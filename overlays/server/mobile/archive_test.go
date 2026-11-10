package mobile

import (
	"archive/zip"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

// files lists stage's files relative to it, with their contents.
func files(t *testing.T, stage string) map[string]string {
	t.Helper()
	found := map[string]string{}
	filepath.Walk(stage, func(path string, info os.FileInfo, err error) error {
		if err == nil && info.Mode().IsRegular() {
			rel, _ := filepath.Rel(stage, path)
			data, _ := os.ReadFile(path)
			found[filepath.ToSlash(rel)] = string(data)
		}
		return nil
	})
	return found
}

var revisionZero = map[string]string{
	"revisions/0/assetbundle/ui/one.assetbundle": "bundle-one",
	"revisions/0/assetbundle/ui/two.assetbundle": "bundle-two",
	"revisions/0/info.json":                      `[{"from-name": "a", "to-revision": 0, "to-name": "b"}]`,
	"revisions/0/list.bin":                       "\x08\x01",
}

func expectRevisionZero(t *testing.T, stage string) {
	t.Helper()
	got := files(t, stage)
	if len(got) != len(revisionZero) {
		names := make([]string, 0, len(got))
		for n := range got {
			names = append(names, n)
		}
		sort.Strings(names)
		t.Fatalf("extracted %v", names)
	}
	for name, want := range revisionZero {
		if got[name] != want {
			t.Fatalf("%s = %q, want %q", name, got[name], want)
		}
	}
}

func TestArchive7zExtractsOnlyRevisionZero(t *testing.T) {
	for _, fixture := range []string{"testdata/dump.7z", "testdata/nested.7z"} {
		stage := t.TempDir()
		decoded := decodedStreams.Swap(0)
		if e := ImportArchive(fixture, stage); e != "" {
			t.Fatalf("%s: %s", fixture, e)
		}
		expectRevisionZero(t, stage)
		// The fixture's third block holds only revision 5; it is never decompressed.
		if decoded = decodedStreams.Load(); decoded != 2 {
			t.Fatalf("%s: decompressed %d blocks, want 2", fixture, decoded)
		}
		var p struct{ Done, Total, Files, TotalFiles int64 }
		json.Unmarshal([]byte(ImportProgress()), &p)
		if p.Total == 0 || p.Done != p.Total || p.TotalFiles != 4 || p.Files != 4 {
			t.Fatalf("progress %+v", p)
		}
	}
}

func writeZip(t *testing.T, path string, entries map[string]string) {
	t.Helper()
	f, _ := os.Create(path)
	w := zip.NewWriter(f)
	for name, data := range entries {
		part, _ := w.Create(name)
		part.Write([]byte(data))
	}
	w.Close()
	f.Close()
}

func TestArchiveZipExtractsOnlyRevisionZero(t *testing.T) {
	root := t.TempDir()
	entries := map[string]string{"assets/revisions/5/info.json": "old", "assets/revisions/5/list.bin": "\x08\x05"}
	for name, data := range revisionZero {
		entries["assets/"+name] = data
	}
	archive := filepath.Join(root, "dump.zip")
	writeZip(t, archive, entries)
	stage := filepath.Join(root, "stage")
	if e := ImportArchive(archive, stage); e != "" {
		t.Fatal(e)
	}
	expectRevisionZero(t, stage)
}

func TestArchiveRejectsUnsafeAndUnknown(t *testing.T) {
	root := t.TempDir()
	unsafe := filepath.Join(root, "unsafe.zip")
	writeZip(t, unsafe, map[string]string{"revisions/0/list.bin": "\x08\x01", "revisions/0/../../escape.txt": "x"})
	if e := ImportArchive(unsafe, filepath.Join(root, "stage")); !strings.Contains(e, "unsafe") {
		t.Fatalf("unsafe path: got %q", e)
	}
	if _, err := os.Stat(filepath.Join(root, "escape.txt")); err == nil {
		t.Fatal("wrote outside the stage")
	}
	empty := filepath.Join(root, "empty.zip")
	writeZip(t, empty, map[string]string{"readme.txt": "hi"})
	if e := ImportArchive(empty, filepath.Join(root, "stage2")); !strings.Contains(e, "revisions/0") {
		t.Fatalf("no revision 0: got %q", e)
	}
	text := filepath.Join(root, "notes.txt")
	os.WriteFile(text, []byte("not an archive"), 0600)
	if e := ImportArchive(text, filepath.Join(root, "stage3")); !strings.Contains(e, ".7z") {
		t.Fatalf("unknown format: got %q", e)
	}
}

func TestArchiveCancel(t *testing.T) {
	CancelImport()
	// A cancel before an import starts does not stick to the next one.
	stage := t.TempDir()
	if e := ImportArchive("testdata/dump.7z", stage); e != "" {
		t.Fatal(e)
	}
	f, _ := os.Open("testdata/dump.7z")
	defer f.Close()
	info, _ := f.Stat()
	importCancelled.Store(true)
	if e := extractArchive(f, info.Size(), t.TempDir(), extractOptions{free: 1 << 50}); e == nil || !strings.Contains(e.Error(), "cancelled") {
		t.Fatalf("cancel: got %v", e)
	}
}

// Android 17 refuses to reopen a picked document through /proc/self/fd, so
// the import must read the descriptor it is given. Here the file is deleted
// after opening: only reading the descriptor itself can succeed.
func TestArchiveFdNeedsNoReopen(t *testing.T) {
	data, _ := os.ReadFile("testdata/nested.7z")
	path := filepath.Join(t.TempDir(), "picked.7z")
	os.WriteFile(path, data, 0600)
	f, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	os.Remove(path)
	stage := t.TempDir()
	if e := ImportArchiveFd(int(f.Fd()), stage); e != "" {
		t.Fatal(e)
	}
	expectRevisionZero(t, stage)
	// The caller's descriptor stays open and usable.
	if _, err := f.ReadAt(make([]byte, 2), 0); err != nil {
		t.Fatalf("caller's descriptor was closed: %v", err)
	}
}

// serveFile serves a file over HTTP with range support, as a download host would.
func serveFile(t *testing.T, path string) string {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.ServeFile(w, r, path)
	}))
	t.Cleanup(srv.Close)
	return srv.URL + "/" + filepath.Base(path)
}

func plenty(t *testing.T) {
	t.Helper()
	old := freeSpace
	freeSpace = func(string) (int64, error) { return 1 << 50, nil }
	t.Cleanup(func() { freeSpace = old })
}

func TestImportLinkExtractsOnlyRevisionZero(t *testing.T) {
	plenty(t)
	stage := filepath.Join(t.TempDir(), "stage")
	decodedStreams.Store(0)
	if e := ImportLink(serveFile(t, "testdata/dump.7z"), stage, -1); e != "" {
		t.Fatal(e)
	}
	expectRevisionZero(t, stage)
	if d := decodedStreams.Load(); d != 2 {
		t.Fatalf("decompressed %d blocks, want 2", d)
	}
	var p struct{ Done, Total, Downloaded int64 }
	json.Unmarshal([]byte(ImportProgress()), &p)
	if p.Downloaded == 0 || p.Done != p.Total {
		t.Fatalf("progress %+v", p)
	}
}

func TestImportSpaceRefused(t *testing.T) {
	old := freeSpace
	freeSpace = func(string) (int64, error) { return 1024, nil }
	defer func() { freeSpace = old }()
	for name, run := range map[string]func(stage string) string{
		"file": func(stage string) string { return ImportArchive("testdata/dump.7z", stage) },
		"link": func(stage string) string { return ImportLink(serveFile(t, "testdata/dump.7z"), stage, -1) },
		"given": func(stage string) string {
			freeSpace = func(string) (int64, error) { return 1 << 50, nil }
			return ImportLink(serveFile(t, "testdata/dump.7z"), stage, 2048)
		},
	} {
		stage := filepath.Join(t.TempDir(), "stage")
		e := run(stage)
		if !strings.HasPrefix(e, "Not enough free space") || !strings.Contains(e, "GB") {
			t.Fatalf("%s: got %q", name, e)
		}
		if _, err := os.Stat(filepath.Join(stage, "revisions")); err == nil {
			t.Fatalf("%s: wrote game files before checking the space", name)
		}
		freeSpace = func(string) (int64, error) { return 1024, nil }
	}
}

// interruptAfterFirstStream cancels the import once one block is finished.
func interruptAfterFirstStream(t *testing.T) {
	old, oldWorkers := afterStream, linkWorkers
	afterStream = func(int) { importCancelled.Store(true) }
	linkWorkers = 1
	t.Cleanup(func() { afterStream, linkWorkers = old, oldWorkers })
}

func TestImportLinkResumeSkipsDoneStreams(t *testing.T) {
	plenty(t)
	link := serveFile(t, "testdata/dump.7z")
	stage := filepath.Join(t.TempDir(), "stage")
	interruptAfterFirstStream(t)
	if e := ImportLink(link, stage, -1); !strings.Contains(e, "kept") {
		t.Fatalf("interrupted import: got %q", e)
	}
	afterStream = nil
	decodedStreams.Store(0)
	if e := ImportLink(link, stage, -1); e != "" {
		t.Fatal(e)
	}
	expectRevisionZero(t, stage)
	if d := decodedStreams.Load(); d != 1 {
		t.Fatalf("resume decompressed %d blocks, want 1", d)
	}
	if _, err := os.Stat(filepath.Join(stage, linkRecordName)); err == nil {
		t.Fatal("the resume record was left in the finished stage")
	}
}

func TestImportLinkResumeSpaceCountsOnlyRemaining(t *testing.T) {
	plenty(t)
	link := serveFile(t, "testdata/dump.7z")
	stage := filepath.Join(t.TempDir(), "stage")
	interruptAfterFirstStream(t)
	ImportLink(link, stage, -1)
	afterStream = nil
	var asked []int64
	old := checkSpaceHook
	checkSpaceHook = func(needed int64) { asked = append(asked, needed) }
	defer func() { checkSpaceHook = old }()
	ImportLink(link, filepath.Join(t.TempDir(), "fresh"), -1)
	ImportLink(link, stage, -1)
	if len(asked) != 2 || asked[1] >= asked[0] {
		t.Fatalf("space asked for %v; the resumed import should need less", asked)
	}
}

func TestImportLinkWrongIDWipesStage(t *testing.T) {
	plenty(t)
	stage := filepath.Join(t.TempDir(), "stage")
	os.MkdirAll(filepath.Join(stage, "revisions/0"), 0700)
	os.WriteFile(filepath.Join(stage, "revisions/0/stale.bin"), []byte("old"), 0600)
	os.WriteFile(filepath.Join(stage, linkRecordName), []byte(`{"id":"http other 5","done":[0,1]}`), 0600)
	decodedStreams.Store(0)
	if e := ImportLink(serveFile(t, "testdata/dump.7z"), stage, -1); e != "" {
		t.Fatal(e)
	}
	expectRevisionZero(t, stage)
	if d := decodedStreams.Load(); d != 2 {
		t.Fatalf("decompressed %d blocks, want 2: the other link's record was trusted", d)
	}
}

func TestImportLinkRejectsHTML(t *testing.T) {
	page := filepath.Join(t.TempDir(), "page.html")
	os.WriteFile(page, []byte("<!DOCTYPE html><html><body>Sign in</body></html>"), 0600)
	e := ImportLink(serveFile(t, page), filepath.Join(t.TempDir(), "stage"), -1)
	if !strings.Contains(e, "web page") {
		t.Fatalf("got %q", e)
	}
}

func TestImportLinkCancelKeepsStage(t *testing.T) {
	plenty(t)
	stage := filepath.Join(t.TempDir(), "stage")
	interruptAfterFirstStream(t)
	ImportLink(serveFile(t, "testdata/dump.7z"), stage, -1)
	record := loadLinkRecord(stage)
	if record == nil || len(record.Done) != 1 || record.Kept <= 0 {
		t.Fatalf("resume record after a cancel: %+v", record)
	}
	if len(files(t, filepath.Join(stage, "revisions"))) == 0 {
		t.Fatal("the finished block's files are gone after a cancel")
	}
}

func TestImportLinkBadLink(t *testing.T) {
	if e := ImportLink("ftp://x/y.7z", t.TempDir(), -1); !strings.Contains(e, "http") {
		t.Fatalf("got %q", e)
	}
}

// A worker's failure stops the other workers through the cancel flag; the
// player must still see the failure, not "Download stopped".
func TestImportLinkReportsRealError(t *testing.T) {
	plenty(t)
	link := serveFile(t, "testdata/dump.7z")
	stage := filepath.Join(t.TempDir(), "stage")
	interruptAfterFirstStream(t)
	ImportLink(link, stage, -1)
	afterStream = nil
	filepath.Walk(filepath.Join(stage, "revisions"), func(p string, info os.FileInfo, err error) error {
		if err == nil && info.IsDir() {
			os.Chmod(p, 0500)
		}
		return nil
	})
	t.Cleanup(func() {
		filepath.Walk(stage, func(p string, info os.FileInfo, err error) error { os.Chmod(p, 0700); return nil })
	})
	e := ImportLink(link, stage, -1)
	if e == "" || strings.Contains(e, "Download stopped") {
		t.Fatalf("got %q, want the write error", e)
	}
}

// iOS counts purgeable space as free; the archive import uses its number.
func TestImportArchiveUsesGivenFreeSpace(t *testing.T) {
	plenty(t)
	if e := ImportArchiveFree("testdata/dump.7z", filepath.Join(t.TempDir(), "s"), 2048); !strings.HasPrefix(e, "Not enough free space") {
		t.Fatalf("got %q", e)
	}
	if e := ImportArchiveFree("testdata/dump.7z", filepath.Join(t.TempDir(), "s"), 1<<50); e != "" {
		t.Fatal(e)
	}
}
