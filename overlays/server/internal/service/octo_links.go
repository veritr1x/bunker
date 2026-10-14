package service

import (
	"crypto/md5"
	"encoding/hex"
	"errors"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"
)

// OctoLinks keeps one copy of each game file on the device. The game saves
// every file it downloads in its own cache (octo/v1/<app>/<bucket>/<hex of
// type letter + object id>/<md5>), byte for byte the file this server sent.
// Once the game has saved a file, its cache entry is replaced with a hard
// link to the server's copy, so both names share the same data on disk.
// Android refuses hard links to apps (SELinux denies "link" to apps targeting
// Android 9 or later), and they cannot cross file systems (game files used in
// place from shared storage, an SD card or another iOS folder); then the entry
// becomes a symbolic link to the server's copy instead. If neither works, the
// first failure turns this off and nothing changes. Symbolic links are
// relative: iOS moves an app's data folder when the app is updated, which left
// absolute links pointing nowhere (the game then downloaded those files on
// every start, and could not save them through the broken links). Such links
// are pointed at the server's copy again when the server starts.
//
// The game writes cache files in place (FileMode.Create, which also follows a
// symbolic link), so before serving a file whose cache entry is a link, the
// entry is removed: a new download then goes to a fresh file and never into
// the server's copy (or through a broken link).
type OctoLinks struct {
	cache    string // octo/v1
	baseDir  string
	platform string
	find     func(objectId, assetType string) []assetCandidate // the server's copies; replaced in tests

	mu       sync.Mutex
	off      bool
	symbolic bool // hard links were refused: link symbolically
	saved    int64
}

// symbolicMinSize: smaller files are left as they are once links are
// symbolic, since a symbolic link takes up a block of its own.
const symbolicMinSize = 4096

// NewOctoLinks links the cache under octoRoot (the game's octo folder) to the
// asset tree under baseDir, for the given platform ("android" or "ios").
func NewOctoLinks(octoRoot, baseDir, platform string) *OctoLinks {
	l := &OctoLinks{cache: filepath.Join(octoRoot, "v1"), baseDir: baseDir, platform: platform}
	l.find = l.candidates
	return l
}

// Wrap serves next, unlinking the cache entry of a file before it is sent and
// linking it again once the game has saved the download.
func (l *OctoLinks) Wrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		objectId, assetType, ok := unsoObject(r.URL.Path)
		if !ok || l.disabled() {
			next.ServeHTTP(w, r)
			return
		}
		l.unlink(objectId, assetType)
		sw := &statusWriter{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(sw, r)
		if sw.status == http.StatusOK {
			go l.linkLater(objectId, assetType)
		}
	})
}

// Sweep links every file already in the cache. Run it in the background: on
// first use it reads each cached file once to check it.
func (l *OctoLinks) Sweep() {
	start := time.Now()
	entries, _ := filepath.Glob(filepath.Join(l.cache, "*", "*", "*"))
	linked := 0
	for _, dir := range entries {
		if l.disabled() {
			return
		}
		objectId, assetType, ok := cacheObject(filepath.Base(dir))
		if !ok {
			continue
		}
		files, _ := os.ReadDir(dir)
		for _, f := range files {
			sum, ok := cacheSum(f.Name())
			if !(f.Type().IsRegular() || f.Type()&os.ModeSymlink != 0) || !ok {
				continue
			}
			if l.link(filepath.Join(dir, f.Name()), objectId, assetType, sum) {
				linked++
			}
		}
	}
	l.mu.Lock()
	saved := l.saved
	l.mu.Unlock()
	if linked > 0 || saved > 0 {
		log.Printf("[OctoLinks] %d cached files linked to the server's copies, %d MB saved, in %s", linked, saved>>20, time.Since(start).Round(time.Millisecond))
	}
}

func (l *OctoLinks) disabled() bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.off
}

// unlink removes cache entries of this object that are links: symbolic ones
// (working or not) and hard links to a server file.
func (l *OctoLinks) unlink(objectId, assetType string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	for _, path := range l.entries(objectId, assetType) {
		if info, err := os.Lstat(path); err == nil && info.Mode()&os.ModeSymlink != 0 {
			if err := os.Remove(path); err != nil {
				log.Printf("[OctoLinks] could not unlink %s before a new download: %v", path, err)
			}
			continue
		}
		cached, err := os.Stat(path)
		if err != nil {
			continue
		}
		for _, c := range l.find(objectId, assetType) {
			if server, err := os.Stat(c.Path); err == nil && os.SameFile(cached, server) {
				if err := os.Remove(path); err != nil {
					log.Printf("[OctoLinks] could not unlink %s before a new download: %v", path, err)
				}
				break
			}
		}
	}
}

// linkLater waits for the game to save a download, then links it.
func (l *OctoLinks) linkLater(objectId, assetType string) {
	for _, wait := range []time.Duration{time.Second, 3 * time.Second, 10 * time.Second, 30 * time.Second} {
		time.Sleep(wait)
		for _, path := range l.entries(objectId, assetType) {
			sum, _ := cacheSum(filepath.Base(path))
			if l.link(path, objectId, assetType, sum) {
				return
			}
		}
	}
}

// entries lists the cache files of one object.
func (l *OctoLinks) entries(objectId, assetType string) []string {
	letter := "A"
	if assetType == "resources" {
		letter = "R"
	}
	name := strings.ToUpper(hex.EncodeToString([]byte(letter + objectId)))
	// Look the folder up in each bucket by name: a pattern would read every
	// bucket in full, over 100,000 entries once the game data is downloaded.
	var files []string
	apps, _ := os.ReadDir(l.cache)
	for _, app := range apps {
		buckets, _ := os.ReadDir(filepath.Join(l.cache, app.Name()))
		for _, bucket := range buckets {
			dir := filepath.Join(l.cache, app.Name(), bucket.Name(), name)
			names, err := os.ReadDir(dir)
			if err != nil {
				continue
			}
			for _, f := range names {
				if _, ok := cacheSum(f.Name()); ok {
					files = append(files, filepath.Join(dir, f.Name()))
				}
			}
		}
	}
	return files
}

func (l *OctoLinks) candidates(objectId, assetType string) []assetCandidate {
	candidates, _, _ := objectIdToFilePathCandidates(l.baseDir, "0", l.platform, assetType, objectId)
	return candidates
}

// link replaces the cache file at path with a link to the server's copy when
// both hold the same bytes. It reports whether the file is now linked.
func (l *OctoLinks) link(path, objectId, assetType, sum string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.off {
		return false
	}
	if entry, err := os.Lstat(path); err == nil && entry.Mode()&os.ModeSymlink != 0 {
		return l.relink(path, objectId, assetType, sum)
	}
	cached, err := os.Stat(path)
	if err != nil || !cached.Mode().IsRegular() {
		return false
	}
	for _, c := range l.find(objectId, assetType) {
		if !strings.EqualFold(c.ExpectedMD5, sum) {
			continue
		}
		server, err := os.Stat(c.Path)
		if err != nil || !server.Mode().IsRegular() {
			continue
		}
		if os.SameFile(cached, server) {
			return true
		}
		if server.Size() != cached.Size() {
			continue
		}
		if l.symbolic && cached.Size() < symbolicMinSize {
			return false // a symbolic link takes as much space as this file
		}
		if actual, err := fileMD5Hex(c.Path, server); err != nil || !strings.EqualFold(actual, sum) {
			continue
		}
		// The game may still be writing: link only a complete, matching file.
		if actual, err := md5Of(path); err != nil || !strings.EqualFold(actual, sum) {
			return false
		}
		temp := filepath.Join(filepath.Dir(path), "."+filepath.Base(path)+".link") // never read as a cache file
		os.Remove(temp)
		if err := l.makeLink(c.Path, temp); err != nil {
			l.off = true
			log.Printf("[OctoLinks] off: %v", err)
			return false
		}
		if err := os.Rename(temp, path); err != nil {
			os.Remove(temp)
			log.Printf("[OctoLinks] could not replace %s: %v", path, err)
			return false
		}
		l.saved += cached.Size()
		return true
	}
	return false
}

// relink keeps a symbolic link that reaches the server's copy by a relative
// path, and points any other (absolute or broken) at that copy again. The
// entry's name is its md5, checked against the server's copy.
func (l *OctoLinks) relink(path, objectId, assetType, sum string) bool {
	if target, err := os.Readlink(path); err == nil && !filepath.IsAbs(target) {
		if _, err := os.Stat(path); err == nil {
			return true
		}
	}
	for _, c := range l.find(objectId, assetType) {
		if !strings.EqualFold(c.ExpectedMD5, sum) {
			continue
		}
		server, err := os.Stat(c.Path)
		if err != nil || !server.Mode().IsRegular() {
			continue
		}
		if actual, err := fileMD5Hex(c.Path, server); err != nil || !strings.EqualFold(actual, sum) {
			continue
		}
		temp := filepath.Join(filepath.Dir(path), "."+filepath.Base(path)+".link")
		os.Remove(temp)
		if err := symlinkRelative(c.Path, temp); err != nil {
			log.Printf("[OctoLinks] could not repair %s: %v", path, err)
			return false
		}
		if err := os.Rename(temp, path); err != nil {
			os.Remove(temp)
			log.Printf("[OctoLinks] could not replace %s: %v", path, err)
			return false
		}
		return true
	}
	// No server copy: let the game download the file again.
	os.Remove(path)
	return false
}

// makeLink links temp to the server's file: a hard link while those work,
// otherwise a symbolic link.
func (l *OctoLinks) makeLink(server, temp string) error {
	if !l.symbolic {
		err := os.Link(server, temp)
		if err == nil || !(errors.Is(err, os.ErrPermission) || isCrossDevice(err)) {
			return err
		}
		log.Printf("[OctoLinks] hard links refused (%v); using symbolic links", err)
		l.symbolic = true
	}
	return symlinkRelative(server, temp)
}

// symlinkRelative makes a symbolic link at link to target by a path relative to
// the link's folder (absolute only if there is none).
func symlinkRelative(target, link string) error {
	absolute, err := filepath.Abs(target)
	if err != nil {
		return err
	}
	dir, err := filepath.Abs(filepath.Dir(link))
	if err != nil {
		return err
	}
	if relative, err := filepath.Rel(dir, absolute); err == nil {
		return os.Symlink(relative, link)
	}
	return os.Symlink(absolute, link)
}

// unsoObject reads the object id and type from an asset URL
// (.../unso-{version}-{assetbundle|resources}/{object_id}).
func unsoObject(path string) (objectId, assetType string, ok bool) {
	parts := strings.Split(strings.Trim(path, "/"), "/")
	for i, p := range parts {
		if strings.HasPrefix(p, "unso-") && i+1 < len(parts) {
			assetType = p[strings.LastIndex(p, "-")+1:]
			if assetType == "assetbundle" || assetType == "resources" {
				return parts[i+1], assetType, parts[i+1] != ""
			}
		}
	}
	return "", "", false
}

// cacheObject decodes a cache folder name: hex of "A" (asset bundle) or "R"
// (resource) followed by the object id.
func cacheObject(name string) (objectId, assetType string, ok bool) {
	raw, err := hex.DecodeString(name)
	if err != nil || len(raw) < 2 {
		return "", "", false
	}
	switch raw[0] {
	case 'A':
		return string(raw[1:]), "assetbundle", true
	case 'R':
		return string(raw[1:]), "resources", true
	}
	return "", "", false
}

// cacheSum reads the md5 a cache file is named by; movies keep their
// extension (<md5>.mp4).
func cacheSum(name string) (string, bool) {
	sum, _, _ := strings.Cut(name, ".")
	if len(sum) != 32 {
		return "", false
	}
	_, err := hex.DecodeString(sum)
	return sum, err == nil
}

func isCrossDevice(err error) bool { return errors.Is(err, syscall.EXDEV) }

func md5Of(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := md5.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(status int) {
	w.status = status
	w.ResponseWriter.WriteHeader(status)
}
