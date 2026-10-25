package main

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/bodgit/sevenzip"
)

// The game files are unpacked on the computer, not in the phone: the Bunker's
// own import runs ARM code through the emulator's translation, which takes
// hours for the 21 GB, against minutes here. This follows the Bunker's import
// (overlays/server/mobile/archive.go): only revision 0 is unpacked, and in a
// 7z only the compressed blocks that hold it are decompressed, several at once.
// Unlike Windows' tar, it keeps the few file names with unusual characters.

// revisionPath maps an archive entry to its place under revisions/0, or "" for
// entries outside it. The dump may sit inside other folders.
func revisionPath(name string) (string, error) {
	parts := strings.Split(strings.ReplaceAll(name, "\\", "/"), "/")
	for i := 0; i+1 < len(parts); i++ {
		if parts[i] != "revisions" || parts[i+1] != "0" {
			continue
		}
		rest := []string{"revisions", "0"}
		for _, p := range parts[i+2:] {
			switch p {
			case "", ".":
			case "..":
				return "", fmt.Errorf("the archive contains an unsafe path: %s", name)
			default:
				rest = append(rest, p)
			}
		}
		if len(rest) == 2 {
			return "", nil
		}
		return path.Join(rest...), nil
	}
	return "", nil
}

// sink receives the files of revision 0, possibly from several goroutines.
type sink interface {
	put(rel string, size int64, r io.Reader) error
}

// dirSink writes the files into a folder.
type dirSink string

func (d dirSink) put(rel string, size int64, r io.Reader) error {
	target := filepath.Join(string(d), filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return err
	}
	w, err := os.Create(target)
	if err != nil {
		return err
	}
	_, err = io.Copy(w, r)
	if cerr := w.Close(); err == nil {
		err = cerr
	}
	return err
}

// tarSink writes the files as one tar stream, for the phone's tar to unpack.
// Files are written whole, one at a time: a small one is read into memory
// first, so the other workers keep decompressing meanwhile.
type tarSink struct {
	mu       sync.Mutex
	tw       *tar.Writer
	dirs     map[string]bool
	uid, gid int
	now      time.Time
}

const smallFile = 16 << 20

func newTarSink(w io.Writer, uid, gid int) *tarSink {
	return &tarSink{tw: tar.NewWriter(w), dirs: map[string]bool{}, uid: uid, gid: gid, now: time.Now()}
}

func (s *tarSink) put(rel string, size int64, r io.Reader) error {
	var data []byte
	if size <= smallFile {
		data = make([]byte, size)
		if _, err := io.ReadFull(r, data); err != nil {
			return err
		}
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := s.mkdirs(path.Dir(rel)); err != nil {
		return err
	}
	hdr := &tar.Header{Typeflag: tar.TypeReg, Name: rel, Size: size, Mode: 0o600, Uid: s.uid, Gid: s.gid, ModTime: s.now}
	if err := s.tw.WriteHeader(hdr); err != nil {
		return err
	}
	if data != nil {
		_, err := s.tw.Write(data)
		return err
	}
	_, err := io.CopyN(s.tw, r, size)
	return err
}

func (s *tarSink) mkdirs(dir string) error {
	if dir == "." || s.dirs[dir] {
		return nil
	}
	if err := s.mkdirs(path.Dir(dir)); err != nil {
		return err
	}
	s.dirs[dir] = true
	return s.tw.WriteHeader(&tar.Header{Typeflag: tar.TypeDir, Name: dir + "/", Mode: 0o700, Uid: s.uid, Gid: s.gid, ModTime: s.now})
}

func (s *tarSink) close() error { return s.tw.Close() }

type extraction struct {
	sink              sink
	done, total       atomic.Int64
	files, totalFiles atomic.Int64
	failed            atomic.Bool
	catalog           atomic.Bool
}

// extractGameFiles unpacks revisions/0 of a .7z or .zip into dest.
func extractGameFiles(archivePath, dest string) error {
	_, err := unpackGameFiles(archivePath, dirSink(dest), nil)
	return err
}

// unpackGameFiles sends revisions/0 of a .7z or .zip to a sink and returns how
// many files it sent. onProgress, if set, is called about every second.
func unpackGameFiles(archivePath string, to sink, onProgress func(done, total int64)) (int64, error) {
	f, err := os.Open(archivePath)
	if err != nil {
		return 0, err
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		return 0, err
	}
	magic := make([]byte, 6)
	n, _ := f.ReadAt(magic, 0)
	x := &extraction{sink: to}
	stop := make(chan struct{})
	shown := make(chan struct{})
	go func() {
		defer close(shown)
		for {
			select {
			case <-stop:
				return
			case <-time.After(time.Second):
				if t := x.total.Load(); t > 0 && onProgress != nil {
					onProgress(x.done.Load(), t)
				}
			}
		}
	}()
	switch {
	case bytes.Equal(magic[:n], []byte("7z\xbc\xaf\x27\x1c")):
		err = x.from7z(f, info.Size())
	case n >= 4 && bytes.Equal(magic[:4], []byte("PK\x03\x04")):
		err = x.fromZip(f, info.Size())
	default:
		err = errors.New("choose a .7z or .zip of the resource dump")
	}
	close(stop)
	<-shown
	if err == nil && !x.catalog.Load() {
		err = errors.New("this archive has no revisions/0/list.bin; choose the Android resource dump")
	}
	return x.files.Load(), err
}

// toRevision finds the revisions an info.json points at.
var toRevision = regexp.MustCompile(`"to-revision"\s*:\s*"?(\d+)`)

func (x *extraction) write(rel string, size int64, open func() (io.ReadCloser, error)) error {
	in, err := open()
	if err != nil {
		return err
	}
	defer in.Close()
	var r io.Reader = &counter{in, &x.done}
	var info bytes.Buffer
	if path.Base(rel) == "info.json" {
		r = io.TeeReader(r, &info)
	}
	if err := x.sink.put(rel, size, r); err != nil {
		return fmt.Errorf("unpacking %s: %w", rel, err)
	}
	// As the Bunker's import does: revision 0 must not point at files kept in
	// other revisions, which this does not unpack.
	for _, m := range toRevision.FindAllSubmatch(info.Bytes(), -1) {
		if string(m[1]) != "0" {
			return errors.New("these game files need files from other revisions too. Prepare them on a computer with scripts/prepare_assets.py")
		}
	}
	if (rel == "revisions/0/list.bin" || rel == "revisions/0/android/list.bin") && size > 0 {
		x.catalog.Store(true)
	}
	x.files.Add(1)
	return nil
}

type counter struct {
	r io.Reader
	n *atomic.Int64
}

func (c *counter) Read(p []byte) (int, error) {
	n, err := c.r.Read(p)
	c.n.Add(int64(n))
	return n, err
}

func (x *extraction) from7z(source io.ReaderAt, size int64) error {
	archive, err := sevenzip.NewReader(source, size)
	if err != nil {
		return fmt.Errorf("cannot read the archive: %w", err)
	}
	// Group revision 0's files by compressed block; other blocks are skipped.
	byStream := map[int][]int{}
	var streams []int
	for i, file := range archive.File {
		rel, err := revisionPath(file.Name)
		if err != nil {
			return err
		}
		if rel == "" || file.FileInfo().IsDir() {
			continue
		}
		if _, seen := byStream[file.Stream]; !seen {
			streams = append(streams, file.Stream)
		}
		byStream[file.Stream] = append(byStream[file.Stream], i)
		x.total.Add(int64(file.UncompressedSize))
		x.totalFiles.Add(1)
	}
	work := make(chan int, len(streams))
	for _, s := range streams {
		work <- s
	}
	close(work)
	// Each LZMA2 decoder holds its dictionary (64 MB for the dump).
	workers := min(runtime.NumCPU(), 8, len(streams))
	var wg sync.WaitGroup
	var once sync.Once
	var first error
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			reader, err := sevenzip.NewReader(source, size)
			if err != nil {
				once.Do(func() { first = err })
				x.failed.Store(true)
				return
			}
			for stream := range work {
				for _, i := range byStream[stream] {
					if x.failed.Load() {
						return
					}
					file := reader.File[i]
					rel, _ := revisionPath(file.Name)
					if err := x.write(rel, int64(file.UncompressedSize), file.Open); err != nil {
						once.Do(func() { first = err })
						x.failed.Store(true)
						return
					}
				}
			}
		}()
	}
	wg.Wait()
	return first
}

func (x *extraction) fromZip(source io.ReaderAt, size int64) error {
	archive, err := zip.NewReader(source, size)
	if err != nil {
		return fmt.Errorf("cannot read the archive: %w", err)
	}
	var files []*zip.File
	for _, file := range archive.File {
		rel, err := revisionPath(file.Name)
		if err != nil {
			return err
		}
		if rel == "" || file.FileInfo().IsDir() || file.Mode()&os.ModeSymlink != 0 {
			continue
		}
		files = append(files, file)
		x.total.Add(int64(file.UncompressedSize64))
		x.totalFiles.Add(1)
	}
	for _, file := range files {
		rel, _ := revisionPath(file.Name)
		if err := x.write(rel, int64(file.UncompressedSize64), file.Open); err != nil {
			return err
		}
	}
	return nil
}
