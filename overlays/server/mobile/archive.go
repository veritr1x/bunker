package mobile

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"

	"github.com/bodgit/sevenzip"
)

// Progress of the current archive import, read by the launcher while it runs.
var (
	importDone, importTotal       atomic.Int64
	importFiles, importTotalFiles atomic.Int64
	importCancelled               atomic.Bool
	decodedStreams                atomic.Int64 // compressed blocks decompressed, for tests
)

var errCancelled = errors.New("Import cancelled. Your previous files were kept.")

// ImportArchive extracts the game files from a .7z or .zip of the resource
// dump into stage, as stage/revisions/0/... Only revision 0 is used: the
// dump's other revisions are old catalogs the server never reads. In a 7z,
// only the compressed blocks that hold revision 0 are decompressed, several
// at a time. Returns "" or an error for the player. The launcher validates
// and installs the staged files as it does for a folder.
func ImportArchive(source, stage string) string {
	importCancelled.Store(false)
	importDone.Store(0)
	importTotal.Store(0)
	importFiles.Store(0)
	importTotalFiles.Store(0)
	if e := extractArchive(source, stage); e != nil {
		return e.Error()
	}
	return ""
}

// ImportProgress reports bytes ("done", "total") and files ("files",
// "totalFiles") for the running import.
func ImportProgress() string {
	b, _ := json.Marshal(map[string]int64{"done": importDone.Load(), "total": importTotal.Load(),
		"files": importFiles.Load(), "totalFiles": importTotalFiles.Load()})
	return string(b)
}

// CancelImport stops the running import at the next file chunk.
func CancelImport() { importCancelled.Store(true) }

// revisionPath maps an archive entry to its place under revisions/0, or ""
// for entries outside it. The dump may sit inside other folders.
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
				return "", fmt.Errorf("The archive contains an unsafe path: %s", name)
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

func extractArchive(source, stage string) error {
	f, e := os.Open(source)
	if e != nil {
		return e
	}
	magic := make([]byte, 6)
	n, _ := io.ReadFull(f, magic)
	f.Close()
	if e = os.MkdirAll(stage, 0700); e != nil {
		return e
	}
	switch {
	case bytes.Equal(magic[:n], []byte("7z\xbc\xaf\x27\x1c")):
		e = extract7z(source, stage)
	case n >= 4 && bytes.Equal(magic[:4], []byte("PK\x03\x04")):
		e = extractZip(source, stage)
	default:
		return errors.New("Choose a .7z or .zip of the resource dump, or its extracted folder")
	}
	if e != nil {
		return e
	}
	for _, catalog := range []string{"revisions/0/list.bin", "revisions/0/android/list.bin", "revisions/0/ios/list.bin"} {
		if s, err := os.Stat(filepath.Join(stage, catalog)); err == nil && s.Size() > 0 {
			return nil
		}
	}
	return errors.New("This archive has no revisions/0/list.bin. Choose the resource dump archive.")
}

// writeEntry copies one entry into stage, counting progress and honouring cancel.
func writeEntry(stage, rel string, open func() (io.ReadCloser, error)) error {
	if importCancelled.Load() {
		return errCancelled
	}
	target := filepath.Join(stage, filepath.FromSlash(rel))
	if e := os.MkdirAll(filepath.Dir(target), 0700); e != nil {
		return e
	}
	in, e := open()
	if e != nil {
		return e
	}
	defer in.Close()
	out, e := os.OpenFile(target, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0600)
	if e != nil {
		return e
	}
	buf := make([]byte, 1<<20)
	for {
		if importCancelled.Load() {
			out.Close()
			return errCancelled
		}
		n, readErr := in.Read(buf)
		if n > 0 {
			if _, e = out.Write(buf[:n]); e != nil {
				out.Close()
				return fmt.Errorf("Not enough free space to import the game files: %w", e)
			}
			importDone.Add(int64(n))
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			out.Close()
			return fmt.Errorf("The archive is damaged (%s): %w", rel, readErr)
		}
	}
	if e = out.Close(); e == nil {
		importFiles.Add(1)
	}
	return e
}

func extract7z(source, stage string) error {
	archive, e := sevenzip.OpenReader(source)
	if e != nil {
		return fmt.Errorf("Cannot read the archive: %w", e)
	}
	// Group revision 0's files by compressed block; other blocks are skipped.
	byStream := map[int][]int{}
	var streams []int
	for i, file := range archive.File {
		rel, err := revisionPath(file.Name)
		if err != nil {
			archive.Close()
			return err
		}
		if rel == "" || file.FileInfo().IsDir() {
			continue
		}
		if _, seen := byStream[file.Stream]; !seen {
			streams = append(streams, file.Stream)
		}
		byStream[file.Stream] = append(byStream[file.Stream], i)
		importTotal.Add(int64(file.UncompressedSize))
		importTotalFiles.Add(1)
	}
	archive.Close()

	work := make(chan int, len(streams))
	for _, s := range streams {
		work <- s
	}
	close(work)
	workers := runtime.NumCPU()
	if workers > 4 {
		workers = 4 // each LZMA2 decoder holds its dictionary (64 MB for the dump)
	}
	if workers > len(streams) {
		workers = len(streams)
	}
	var wg sync.WaitGroup
	var once sync.Once
	var first error
	fail := func(err error) {
		once.Do(func() { first = err; importCancelled.Store(true) })
	}
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			// Each worker reads its blocks in archive order with its own reader.
			reader, err := sevenzip.OpenReader(source)
			if err != nil {
				fail(err)
				return
			}
			defer reader.Close()
			for stream := range work {
				decodedStreams.Add(1)
				for _, i := range byStream[stream] {
					file := reader.File[i]
					rel, _ := revisionPath(file.Name)
					if err := writeEntry(stage, rel, file.Open); err != nil {
						fail(err)
						return
					}
				}
			}
		}()
	}
	wg.Wait()
	return first
}

func extractZip(source, stage string) error {
	archive, e := zip.OpenReader(source)
	if e != nil {
		return fmt.Errorf("Cannot read the archive: %w", e)
	}
	defer archive.Close()
	type entry struct {
		rel  string
		file *zip.File
	}
	var entries []entry
	for _, file := range archive.File {
		rel, err := revisionPath(file.Name)
		if err != nil {
			return err
		}
		if rel == "" || file.FileInfo().IsDir() || file.Mode()&os.ModeSymlink != 0 {
			continue
		}
		entries = append(entries, entry{rel, file})
		importTotal.Add(int64(file.UncompressedSize64))
		importTotalFiles.Add(1)
	}
	for _, en := range entries {
		if e := writeEntry(stage, en.rel, en.file.Open); e != nil {
			return e
		}
	}
	return nil
}
