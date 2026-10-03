package mobile

import (
	"archive/zip"
	"encoding/json"
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
	importCancelled.Store(true)
	if e := extractArchive("testdata/dump.7z", t.TempDir()); e == nil || !strings.Contains(e.Error(), "cancelled") {
		t.Fatalf("cancel: got %v", e)
	}
}
