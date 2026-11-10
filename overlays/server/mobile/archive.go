package mobile

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/bodgit/sevenzip"

	"lunar-tear/server/mobile/remotefile"
)

// Progress of the current archive import, read by the launcher while it runs.
var (
	importDone, importTotal       atomic.Int64
	importFiles, importTotalFiles atomic.Int64
	importCancelled               atomic.Bool  // stops the workers: the player cancelled, or one failed
	userCancelled                 atomic.Bool  // the player cancelled
	decodedStreams                atomic.Int64 // compressed blocks decompressed, for tests
)

var errCancelled = errors.New("Import cancelled. Your previous files were kept.")

// spaceMargin is kept free beyond the game files, as the iOS launcher's own checks do.
const spaceMargin = 1_000_000_000

// Test hooks: afterStream runs when a block is finished; checkSpaceHook sees
// each space check's need.
var (
	afterStream    func(stream int)
	checkSpaceHook func(needed int64)
)

// linkSource is the link being imported, for the download count in ImportProgress.
var linkSource atomic.Pointer[remotefile.File]

// ImportArchive extracts the game files from a .7z or .zip of the resource
// dump into stage, as stage/revisions/0/... Only revision 0 is used: the
// dump's other revisions are old catalogs the server never reads. In a 7z,
// only the compressed blocks that hold revision 0 are decompressed, several
// at a time. Returns "" or an error for the player. The launcher validates
// and installs the staged files as it does for a folder.
func ImportArchive(source, stage string) string { return ImportArchiveFree(source, stage, -1) }

// ImportArchiveFree is ImportArchive with the free space as the platform
// counts it (iOS includes space it can free on demand), or -1 to measure it.
func ImportArchiveFree(source, stage string, freeBytes int64) string {
	f, e := os.Open(source)
	if e != nil {
		return e.Error()
	}
	defer f.Close()
	return importFile(f, stage, freeBytes)
}

// ImportArchiveFd is ImportArchive for a file the caller already opened, such
// as a document Android's picker granted. Android 17 refuses to reopen those
// through /proc/self/fd, so the descriptor itself is read. The caller keeps
// ownership of fd; a duplicate is used here.
func ImportArchiveFd(fd int, stage string) string {
	f, e := dupFile(fd, "archive")
	if e != nil {
		return fmt.Sprintf("Cannot read the selected archive: %v", e)
	}
	defer f.Close()
	return importFile(f, stage, -1)
}

func importFile(f *os.File, stage string, freeBytes int64) string {
	defer releaseMemory() // up to four LZMA2 decoders of 64 MB each
	resetProgress()
	info, e := f.Stat()
	if e != nil {
		return e.Error()
	}
	if e := extractArchive(f, info.Size(), stage, extractOptions{free: freeBytes}); e != nil {
		return e.Error()
	}
	return ""
}

func resetProgress() {
	importCancelled.Store(false)
	userCancelled.Store(false)
	importDone.Store(0)
	importTotal.Store(0)
	importFiles.Store(0)
	importTotalFiles.Store(0)
	linkSource.Store(nil)
}

// ImportLink unpacks the game files from a link to a .7z or .zip of the
// resource dump, into stage as ImportArchive does. Only the compressed blocks
// holding revision 0 are downloaded, and the archive is never stored. The
// free space (freeBytes, or the stage's file system's when -1) is checked
// before any game data is downloaded.
//
// Each finished block is recorded in stage, which is kept when the import
// fails or is cancelled: the next import from the same link skips those
// blocks. A stage from another link is cleared first.
func ImportLink(link, stage string, freeBytes int64) string {
	defer releaseMemory()
	resetProgress()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go func() { // CancelImport also stops downloads waiting to retry
		for ctx.Err() == nil {
			if importCancelled.Load() {
				cancel()
				return
			}
			time.Sleep(200 * time.Millisecond)
		}
	}()
	f, e := remotefile.Open(ctx, link, nil)
	if e != nil {
		if userCancelled.Load() {
			return errCancelled.Error()
		}
		return e.Error()
	}
	defer f.Close()
	linkSource.Store(f)
	record := loadLinkRecord(stage)
	if record == nil || record.ID != f.ID() {
		if e := os.RemoveAll(stage); e != nil {
			return e.Error()
		}
		record = &linkRecord{ID: f.ID(), URL: link}
	}
	record.path = filepath.Join(stage, linkRecordName)
	if e := os.MkdirAll(stage, 0700); e != nil {
		return e.Error()
	}
	if e := record.save(); e != nil {
		return e.Error()
	}
	workers := linkWorkers
	if f.Host() == "mega" {
		workers = 1 // Mega's limit is per account; one block finishes soonest
	}
	e = extractArchive(f, f.Size(), stage, extractOptions{free: freeBytes, link: record, workers: workers})
	// A failing worker also stops the others through importCancelled; only
	// the player's cancel is "stopped", anything else is the failure itself.
	if e != nil && userCancelled.Load() {
		return errLinkStopped.Error()
	}
	if e != nil {
		return e.Error()
	}
	os.Remove(record.path)
	return ""
}

// linkWorkers caps the blocks a link import unpacks at once, so blocks finish
// (and are kept for resuming) early.
var linkWorkers = 2

var errLinkStopped = errors.New("Download stopped. The finished parts are kept: choose the same link again to continue.")

// linkRecordName is the resume record in a link import's stage.
const linkRecordName = ".link-import.json"

// linkRecord lists the blocks of a link import that are fully on disk.
type linkRecord struct {
	ID   string `json:"id"`
	URL  string `json:"url"`
	Done []int  `json:"done"`
	Kept int64  `json:"kept"` // bytes of the finished blocks, which the launchers show
	path string
	mu   sync.Mutex // guards Done and Kept
	disk sync.Mutex // one save at a time: they share the temporary file
}

func loadLinkRecord(stage string) *linkRecord {
	raw, e := os.ReadFile(filepath.Join(stage, linkRecordName))
	if e != nil {
		return nil
	}
	var r linkRecord
	if json.Unmarshal(raw, &r) != nil {
		return nil
	}
	return &r
}

func (r *linkRecord) done(stream int) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, d := range r.Done {
		if d == stream {
			return true
		}
	}
	return false
}

// finish records a block once its files are written through to storage.
func (r *linkRecord) finish(stream int, bytes int64) error {
	syscall.Sync()
	r.mu.Lock()
	r.Done = append(r.Done, stream)
	r.Kept += bytes
	r.mu.Unlock()
	return r.save()
}

func (r *linkRecord) save() error {
	r.disk.Lock()
	defer r.disk.Unlock()
	r.mu.Lock()
	raw, _ := json.Marshal(r)
	r.mu.Unlock()
	tmp := r.path + ".tmp"
	if e := os.WriteFile(tmp, raw, 0600); e != nil {
		return e
	}
	return os.Rename(tmp, r.path)
}

// extractOptions: free is the free space in bytes, or -1 to measure the
// stage's file system; link is set for a link import; workers caps the
// blocks unpacked at once (0: up to 4).
type extractOptions struct {
	free    int64
	link    *linkRecord
	workers int
}

// checkSpace refuses an import that would not fit, before it writes anything.
func checkSpace(stage string, remaining int64, opt extractOptions) error {
	needed := remaining + spaceMargin
	if checkSpaceHook != nil {
		checkSpaceHook(needed)
	}
	free := opt.free
	if free < 0 {
		var e error
		if free, e = freeSpace(stage); e != nil {
			return nil // unknown: the write errors still say when space runs out
		}
	}
	if free < needed {
		return fmt.Errorf("Not enough free space: the game files need %.1f GB and %.1f GB is free.", float64(needed)/1e9, float64(free)/1e9)
	}
	return nil
}

// dupFile wraps a duplicate of fd, so closing it leaves the caller's open.
func dupFile(fd int, name string) (*os.File, error) {
	dup, e := syscall.Dup(fd)
	if e != nil {
		return nil, e
	}
	return os.NewFile(uintptr(dup), name), nil
}

// ImportProgress reports bytes ("done", "total") and files ("files",
// "totalFiles") for the running import, and for a link the bytes downloaded
// ("downloaded").
func ImportProgress() string {
	var downloaded int64
	if f := linkSource.Load(); f != nil {
		downloaded = f.Received()
	}
	b, _ := json.Marshal(map[string]int64{"done": importDone.Load(), "total": importTotal.Load(),
		"files": importFiles.Load(), "totalFiles": importTotalFiles.Load(), "downloaded": downloaded})
	return string(b)
}

// publishTotals sets the import's size once the whole archive is listed, so the
// launcher never estimates time left from a partial total.
func publishTotals(bytes, files int64) {
	importTotalFiles.Store(files)
	importTotal.Store(bytes)
}

// CancelImport stops the running import at the next file chunk.
func CancelImport() { userCancelled.Store(true); importCancelled.Store(true) }

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

// extractArchive reads the archive only with ReadAt, which several workers can
// share safely, so the file is never reopened.
func extractArchive(f io.ReaderAt, size int64, stage string, opt extractOptions) error {
	magic := make([]byte, 6)
	n, readErr := f.ReadAt(magic, 0)
	if e := os.MkdirAll(stage, 0700); e != nil {
		return e
	}
	var e error
	switch {
	case bytes.Equal(magic[:n], []byte("7z\xbc\xaf\x27\x1c")):
		e = extract7z(f, size, stage, opt)
	case n >= 4 && bytes.Equal(magic[:4], []byte("PK\x03\x04")):
		e = extractZip(f, size, stage, opt)
	case opt.link != nil && n == 0 && readErr != nil && readErr != io.EOF:
		return readErr
	case opt.link != nil:
		return errors.New("The link leads to a web page, not to a .7z or .zip. Copy the link of the archive file itself.")
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
func writeEntry(stage, rel string, open func() (io.ReadCloser, error), link bool) error {
	if importCancelled.Load() {
		return errCancelled
	}
	target := filepath.Join(stage, filepath.FromSlash(rel))
	if e := os.MkdirAll(filepath.Dir(target), 0700); e != nil {
		return e
	}
	in, e := open()
	if e != nil {
		if importCancelled.Load() {
			return errCancelled
		}
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
			if importCancelled.Load() {
				return errCancelled
			}
			if link {
				return fmt.Errorf("The download failed (%s): %w", rel, readErr)
			}
			return fmt.Errorf("The archive is damaged (%s): %w", rel, readErr)
		}
	}
	if e = out.Close(); e == nil {
		importFiles.Add(1)
	}
	return e
}

func extract7z(source io.ReaderAt, size int64, stage string, opt extractOptions) error {
	archive, e := sevenzip.NewReader(source, size)
	if e != nil {
		return fmt.Errorf("Cannot read the archive: %w", e)
	}
	// Group revision 0's files by compressed block; other blocks are skipped.
	byStream := map[int][]int{}
	streamBytes := map[int]int64{}
	var streams []int
	var totalBytes, totalFiles int64
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
		streamBytes[file.Stream] += int64(file.UncompressedSize)
		totalBytes += int64(file.UncompressedSize)
		totalFiles++
	}
	// A resumed link import skips the blocks already on disk.
	var todo []int
	var skippedBytes, skippedFiles int64
	for _, s := range streams {
		if opt.link != nil && opt.link.done(s) {
			skippedBytes += streamBytes[s]
			skippedFiles += int64(len(byStream[s]))
			continue
		}
		todo = append(todo, s)
	}
	if e := checkSpace(stage, totalBytes-skippedBytes, opt); e != nil {
		return e
	}
	publishTotals(totalBytes, totalFiles)
	importDone.Add(skippedBytes)
	importFiles.Add(skippedFiles)
	if opt.link != nil {
		// The largest block first, so one finishes as early as it can.
		sort.SliceStable(todo, func(a, b int) bool { return streamBytes[todo[a]] > streamBytes[todo[b]] })
	}
	streams = todo
	if len(streams) == 0 {
		return nil
	}

	work := make(chan int, len(streams))
	for _, s := range streams {
		work <- s
	}
	close(work)
	workers := runtime.NumCPU()
	if workers > 4 {
		workers = 4 // each LZMA2 decoder holds its dictionary (64 MB for the dump)
	}
	if opt.workers > 0 && workers > opt.workers {
		workers = opt.workers
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
			reader, err := sevenzip.NewReader(source, size)
			if err != nil {
				fail(err)
				return
			}
			for stream := range work {
				decodedStreams.Add(1)
				for _, i := range byStream[stream] {
					file := reader.File[i]
					rel, _ := revisionPath(file.Name)
					if err := writeEntry(stage, rel, file.Open, opt.link != nil); err != nil {
						fail(err)
						return
					}
				}
				if opt.link != nil {
					if err := opt.link.finish(stream, streamBytes[stream]); err != nil {
						fail(err)
						return
					}
				}
				if afterStream != nil {
					afterStream(stream)
				}
			}
		}()
	}
	wg.Wait()
	return first
}

func extractZip(source io.ReaderAt, size int64, stage string, opt extractOptions) error {
	archive, e := zip.NewReader(source, size)
	if e != nil {
		return fmt.Errorf("Cannot read the archive: %w", e)
	}
	type entry struct {
		rel  string
		file *zip.File
	}
	var entries []entry
	var totalBytes, skippedBytes, skippedFiles int64
	for _, file := range archive.File {
		rel, err := revisionPath(file.Name)
		if err != nil {
			return err
		}
		if rel == "" || file.FileInfo().IsDir() || file.Mode()&os.ModeSymlink != 0 {
			continue
		}
		totalBytes += int64(file.UncompressedSize64)
		// A resumed link import keeps the entries already written in full.
		if opt.link != nil {
			if s, err := os.Stat(filepath.Join(stage, filepath.FromSlash(rel))); err == nil && s.Mode().IsRegular() && s.Size() == int64(file.UncompressedSize64) {
				skippedBytes += s.Size()
				skippedFiles++
				continue
			}
		}
		entries = append(entries, entry{rel, file})
	}
	if e := checkSpace(stage, totalBytes-skippedBytes, opt); e != nil {
		return e
	}
	publishTotals(totalBytes, int64(len(entries))+skippedFiles)
	importDone.Add(skippedBytes)
	importFiles.Add(skippedFiles)
	for _, en := range entries {
		if e := writeEntry(stage, en.rel, en.file.Open, opt.link != nil); e != nil {
			return e
		}
	}
	return nil
}
