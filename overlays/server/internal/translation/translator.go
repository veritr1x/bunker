package translation

import (
	"bytes"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
)

// Translator serves the active language pack: list requests get the original
// list.bin with the translated bundles' entries and a higher revision, and
// those bundles are served from their own folder. Everything else, and
// everything while no pack was ever used, passes through untouched.
type Translator struct {
	packPath, buildsDir, statePath string
	assetsRevision, listPath       string
	rebuild                        Rebuilder

	mu       sync.Mutex
	ready    bool   // list.bin was read
	listMD5  string // of the original list.bin
	original uint64 // its revision
	entries  []Entry
	active   bool      // a pack is active
	target   *Manifest // the active pack's finished build
	served   *Manifest // the build named by the last list served (nil: the originals)
	done     chan struct{}
}

// New reads the active pack from <assetRoot>/translation/active.json, keeps
// builds under <assetRoot>/translation/build and the served revision in
// <dataRoot>/translation-state.json. platform ("android" or "ios") picks the
// platform's tree (revisions/0/<platform>/) when it has a list.bin, else the
// shared tree, as the server's own list serving does.
func New(assetRoot, dataRoot, platform string) *Translator {
	assets := filepath.Join(assetRoot, "assets", "revisions", "0")
	if _, err := os.Stat(filepath.Join(assets, platform, "list.bin")); platform != "" && err == nil {
		assets = filepath.Join(assets, platform)
	}
	list := filepath.Join(assets, "list.bin")
	return &Translator{
		packPath:       filepath.Join(assetRoot, "translation", "active.json"),
		buildsDir:      filepath.Join(assetRoot, "translation", "build"),
		statePath:      filepath.Join(dataRoot, "translation-state.json"),
		assetsRevision: assets,
		listPath:       list,
		rebuild:        DefaultRebuilder,
		done:           make(chan struct{}),
	}
}

// Start reads list.bin and the active pack. A pack whose build is not on disk
// yet is built in the background; until then the last served list stays.
func (t *Translator) Start() {
	data, err := os.ReadFile(t.listPath)
	var entries []Entry
	if err == nil {
		t.original, entries, err = ParseList(data)
	}
	if err != nil {
		log.Printf("[Translation] off: %v", err)
		close(t.done)
		return
	}
	for _, e := range entries { // only these are ever translated: about 6,600 of 200,000
		if strings.HasPrefix(e.Path, englishTextPrefix) {
			t.entries = append(t.entries, e)
		}
	}
	sum := md5.Sum(data)
	t.listMD5 = hex.EncodeToString(sum[:])
	t.ready = true
	if id := t.storedFingerprint(); id != "" {
		if m, err := LoadManifest(filepath.Join(t.buildsDir, id)); err == nil && m.ListMD5 == t.listMD5 {
			t.served = m
		}
	}
	pack, err := t.loadPack()
	if err != nil {
		log.Printf("[Translation] pack not used: %v", err)
	}
	if pack == nil {
		t.cleanup()
		close(t.done)
		return
	}
	t.active = true
	id := BuildID(pack.Hash, t.listMD5)
	if m, err := LoadManifest(filepath.Join(t.buildsDir, id)); err == nil {
		t.target = m
		t.cleanup()
		close(t.done)
		return
	}
	log.Printf("[Translation] building %s (%d texts, %d left out)", pack.Language, len(pack.Game), pack.Dropped)
	go func() {
		defer close(t.done)
		m, err := Build(t.assetsRevision, t.entries, t.listMD5, pack, filepath.Join(t.buildsDir, id), t.rebuild)
		if err != nil {
			log.Printf("[Translation] build failed: %v", err)
			return
		}
		log.Printf("[Translation] %s ready: %d bundles, %d kept in English", pack.Language, len(m.Entries), len(m.Skipped))
		t.mu.Lock()
		t.target = m
		t.mu.Unlock()
		t.cleanup()
	}()
}

// wait returns once Start's build, if any, has finished.
func (t *Translator) wait() { <-t.done }

func (t *Translator) loadPack() (*Pack, error) {
	if _, err := os.Stat(t.packPath); errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	return LoadPack(t.packPath)
}

func (t *Translator) storedFingerprint() string {
	data, err := os.ReadFile(t.statePath)
	if err != nil {
		return ""
	}
	var s state
	if json.Unmarshal(data, &s) != nil || strings.HasPrefix(s.Fingerprint, "none:") {
		return ""
	}
	return s.Fingerprint
}

// cleanup removes builds other than the target and the one last served.
func (t *Translator) cleanup() {
	t.mu.Lock()
	keep := map[string]bool{}
	for _, m := range []*Manifest{t.target, t.served} {
		if m != nil {
			keep[m.ID] = true
		}
	}
	t.mu.Unlock()
	dirs, _ := os.ReadDir(t.buildsDir)
	for _, d := range dirs {
		if !keep[d.Name()] {
			os.RemoveAll(filepath.Join(t.buildsDir, d.Name()))
		}
	}
}

func isListPath(path string) bool {
	return strings.HasPrefix(path, "/v1/list/") || (strings.HasPrefix(path, "/v2/") && strings.Contains(path, "/list/"))
}

// requestedRevision is the revision the game last stored, the list request's
// last path segment (/v1/list/<version>/<revision>); 0 when there is none.
func requestedRevision(path string) uint64 {
	n, err := strconv.ParseUint(path[strings.LastIndex(path, "/")+1:], 10, 64)
	if err != nil {
		return 0
	}
	return n
}

// assetObject is the object id of an asset bundle request (…/unso-<v>-assetbundle/<id>).
func assetObject(path string) (string, bool) {
	parts := strings.Split(strings.Trim(path, "/"), "/")
	for i, p := range parts {
		if strings.HasPrefix(p, "unso-") && strings.HasSuffix(p, "-assetbundle") && i+1 < len(parts) && parts[i+1] != "" {
			return parts[i+1], true
		}
	}
	return "", false
}

type captureWriter struct {
	header http.Header
	status int
	body   bytes.Buffer
}

func (c *captureWriter) Header() http.Header         { return c.header }
func (c *captureWriter) WriteHeader(status int)      { c.status = status }
func (c *captureWriter) Write(b []byte) (int, error) { return c.body.Write(b) }

// Wrap serves list and asset requests for the translation and passes the rest to next.
func (t *Translator) Wrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if isListPath(r.URL.Path) {
			t.serveList(w, r, next)
			return
		}
		if id, ok := assetObject(r.URL.Path); ok && t.serveAsset(w, r, id) {
			return
		}
		next.ServeHTTP(w, r)
	})
}

// choose is the build the next list names: the active pack's when finished,
// the last served while it is being built, else none (the originals).
func (t *Translator) choose() *Manifest {
	switch {
	case !t.active:
		return nil
	case t.target != nil:
		return t.target
	default:
		return t.served
	}
}

func (t *Translator) serveList(w http.ResponseWriter, r *http.Request, next http.Handler) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if !t.ready {
		next.ServeHTTP(w, r)
		return
	}
	m := t.choose()
	requested := requestedRevision(r.URL.Path)
	if _, err := os.Stat(t.statePath); m == nil && errors.Is(err, os.ErrNotExist) && requested <= t.original {
		next.ServeHTTP(w, r) // never translated: the list as it always was
		return
	}
	c := &captureWriter{header: http.Header{}, status: http.StatusOK}
	next.ServeHTTP(c, r)
	body := c.body.Bytes()
	if c.status == http.StatusOK {
		fingerprint, changes := "none:"+t.listMD5, map[string]Entry(nil)
		if m != nil {
			fingerprint, changes = m.ID, m.Entries
		}
		revision, err := ServedRevision(t.statePath, t.original, requested, fingerprint)
		if err == nil {
			var out []byte
			if out, err = PatchList(body, revision, changes); err == nil {
				body = out
				t.served = m
				log.Printf("[Translation] list revision %d, %d translated bundles", revision, len(changes))
			}
		}
		if err != nil {
			log.Printf("[Translation] list served unchanged: %v", err)
		}
	}
	for k, v := range c.header {
		w.Header()[k] = v
	}
	w.Header().Set("Content-Length", strconv.Itoa(len(body)))
	w.WriteHeader(c.status)
	w.Write(body)
}

// serveAsset sends a translated bundle named by the list the game holds (the
// last one served); false when that list names the original. A finished build
// the game has not been given a list for yet is never served: its bytes would
// not match the size, CRC and md5 the game expects.
func (t *Translator) serveAsset(w http.ResponseWriter, r *http.Request, id string) bool {
	t.mu.Lock()
	var dir string
	if m := t.served; m != nil {
		if _, ok := m.Entries[id]; ok {
			dir = filepath.Join(t.buildsDir, m.ID)
		}
	}
	t.mu.Unlock()
	if dir == "" {
		return false
	}
	f, err := os.Open(filepath.Join(dir, id+".assetbundle"))
	if err != nil {
		return false
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		return false
	}
	w.Header().Set("Content-Type", "application/octet-stream")
	http.ServeContent(w, r, id+".assetbundle", info.ModTime(), f)
	return true
}
