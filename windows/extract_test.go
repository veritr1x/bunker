package main

import (
	"archive/tar"
	"bytes"
	"io"
	"os"
	"path"
	"path/filepath"
	"strings"
	"testing"
)

// The Bunker's own import fixtures (overlays/server/mobile/testdata): revision 0
// in two blocks and revision 5 in a third, at the top or inside another folder.
var revisionZero = map[string]string{
	"revisions/0/assetbundle/ui/one.assetbundle": "bundle-one",
	"revisions/0/assetbundle/ui/two.assetbundle": "bundle-two",
	"revisions/0/info.json":                      `[{"from-name": "a", "to-revision": 0, "to-name": "b"}]`,
	"revisions/0/list.bin":                       "\x08\x01",
}

func filesUnder(t *testing.T, root string) map[string]string {
	t.Helper()
	found := map[string]string{}
	filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() {
			rel, _ := filepath.Rel(root, path)
			data, _ := os.ReadFile(path)
			found[filepath.ToSlash(rel)] = string(data)
		}
		return nil
	})
	return found
}

func TestExtract7zTakesOnlyRevisionZero(t *testing.T) {
	for _, fixture := range []string{"testdata/dump.7z", "testdata/nested.7z"} {
		dest := t.TempDir()
		if err := extractGameFiles(fixture, dest); err != nil {
			t.Fatalf("%s: %v", fixture, err)
		}
		got := filesUnder(t, dest)
		if len(got) != len(revisionZero) {
			t.Fatalf("%s: extracted %v", fixture, got)
		}
		for name, want := range revisionZero {
			if got[name] != want {
				t.Fatalf("%s: %s = %q, want %q", fixture, name, got[name], want)
			}
		}
	}
}

// Windows' tar skips names like this one (43 of them in the real dump); they
// must come through.
func TestExtractKeepsUnusualNames(t *testing.T) {
	odd := "revisions/0/assetbundle/2d/chï¼\u009f_bg_road.assetbundle"
	archive := makeZip(t, map[string]string{
		"dump/revisions/0/list.bin": "\x08\x01",
		"dump/" + odd:               "road",
		"dump/revisions/5/old.bin":  "old",
	})
	dest := t.TempDir()
	if err := extractGameFiles(archive, dest); err != nil {
		t.Fatal(err)
	}
	got := filesUnder(t, dest)
	if got[odd] != "road" || len(got) != 2 {
		t.Fatalf("extracted %v", got)
	}
}

func TestTarStream(t *testing.T) {
	odd := "revisions/0/assetbundle/2d/chï¼\u009f_bg_road.assetbundle"
	big := strings.Repeat("m", smallFile+1) // streamed rather than read into memory
	archive := makeZip(t, map[string]string{
		"revisions/0/list.bin":            "\x08\x01",
		odd:                               "road",
		"revisions/0/resources/movie.mp4": big,
		"revisions/3/old.bin":             "old",
	})
	var out bytes.Buffer
	stream := newTarSink(&out, 10205, 10205)
	count, err := unpackGameFiles(archive, stream, nil)
	if err != nil || count != 3 {
		t.Fatalf("%d files, %v", count, err)
	}
	stream.close()
	r := tar.NewReader(&out)
	files, dirs := map[string]string{}, map[string]bool{}
	for {
		h, err := r.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		if h.Uid != 10205 || h.Gid != 10205 {
			t.Errorf("%s belongs to %d:%d", h.Name, h.Uid, h.Gid)
		}
		if h.Typeflag == tar.TypeDir {
			dirs[strings.TrimSuffix(h.Name, "/")] = true
			continue
		}
		if !dirs[path.Dir(h.Name)] {
			t.Errorf("%s comes before its folder", h.Name)
		}
		data, _ := io.ReadAll(r)
		files[h.Name] = string(data)
	}
	if len(files) != 3 || files[odd] != "road" || files["revisions/0/resources/movie.mp4"] != big {
		t.Fatalf("stream holds %d files: %q", len(files), files[odd])
	}
}

func TestRefusesRevisionZeroPointingElsewhere(t *testing.T) {
	archive := makeZip(t, map[string]string{
		"revisions/0/list.bin":  "\x08\x01",
		"revisions/0/info.json": `[{"from-name": "a", "to-revision": 12, "to-name": "b"}]`,
	})
	if err := extractGameFiles(archive, t.TempDir()); err == nil || !strings.Contains(err.Error(), "other revisions") {
		t.Fatalf("accepted revision 0 pointing at revision 12: %v", err)
	}
}

func TestExtractRefusesOtherArchives(t *testing.T) {
	if err := extractGameFiles(makeZip(t, map[string]string{"a.txt": "x"}), t.TempDir()); err == nil {
		t.Fatal("accepted an archive without revisions/0/list.bin")
	}
	plain := filepath.Join(t.TempDir(), "x.7z")
	os.WriteFile(plain, []byte("not an archive"), 0o644)
	if err := extractGameFiles(plain, t.TempDir()); err == nil {
		t.Fatal("accepted a file that is not an archive")
	}
	if _, err := revisionPath("dump/revisions/0/../../evil"); err == nil {
		t.Fatal("accepted an unsafe path")
	}
}
