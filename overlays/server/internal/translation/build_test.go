package translation

import (
	"bytes"
	"crypto/md5"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

// fakeAssets is an assets revision folder with one file per list path.
func fakeAssets(t *testing.T, paths ...string) (string, []Entry) {
	dir := t.TempDir()
	var entries []Entry
	for i, p := range paths {
		file := filepath.Join(dir, "assetbundle", strings.ReplaceAll(p, ")", "/")+".assetbundle")
		if err := os.MkdirAll(filepath.Dir(file), 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(file, []byte("raw "+p), 0644); err != nil {
			t.Fatal(err)
		}
		entries = append(entries, Entry{ObjectID: string(rune('a'+i)) + "00000", Path: p, Size: 1, CRC: 1, MD5: "x"})
	}
	return dir, entries
}

// fakeRebuild uppercases text)en)ui, fails text)en)bad, leaves the rest unchanged, and records what it read.
func fakeRebuild(read *[]string) Rebuilder {
	return func(raw []byte, name string, values map[string]string) ([]byte, uint32, bool, error) {
		*read = append(*read, name)
		switch name {
		case "text)en)ui":
			return bytes.ToUpper(raw), 42, true, nil
		case "text)en)bad":
			return nil, 0, false, errors.New("corrupt")
		}
		return nil, 0, false, nil
	}
}

var testPack = &Pack{Language: "pt", Hash: "packhash", Game: map[string]string{"k": "v"}}

func TestBuildWritesChangedBundlesAndManifest(t *testing.T) {
	assets, entries := fakeAssets(t, "text)en)ui", "text)en)same")
	out := t.TempDir()
	var read []string
	m, err := Build(assets, entries, "listmd5", testPack, out, fakeRebuild(&read))
	if err != nil {
		t.Fatal(err)
	}
	if len(m.Entries) != 1 {
		t.Fatalf("entries %v", m.Entries)
	}
	data, err := os.ReadFile(filepath.Join(out, entries[0].ObjectID+".assetbundle"))
	if err != nil || string(data) != "RAW TEXT)EN)UI" {
		t.Fatalf("%q %v", data, err)
	}
	sum := md5.Sum(data)
	want := Entry{ObjectID: entries[0].ObjectID, Path: "text)en)ui", Size: uint64(len(data)), CRC: 42, MD5: hex.EncodeToString(sum[:])}
	if m.Entries[entries[0].ObjectID] != want {
		t.Fatalf("got %+v want %+v", m.Entries[entries[0].ObjectID], want)
	}
	if m.ID != BuildID("packhash", "listmd5") || m.PackHash != "packhash" || m.ListMD5 != "listmd5" {
		t.Fatalf("%+v", m)
	}
	back, err := LoadManifest(out)
	if err != nil || back.Entries[entries[0].ObjectID] != want {
		t.Fatalf("%+v %v", back, err)
	}
}

func TestBuildSkipsFailures(t *testing.T) {
	assets, entries := fakeAssets(t, "text)en)bad", "text)en)ui")
	entries = append(entries, Entry{ObjectID: "zz0000", Path: "text)en)missing"})
	var read []string
	m, err := Build(assets, entries, "listmd5", testPack, t.TempDir(), fakeRebuild(&read))
	if err != nil {
		t.Fatal(err)
	}
	sort.Strings(m.Skipped)
	if len(m.Entries) != 1 || strings.Join(m.Skipped, ",") != "text)en)bad,text)en)missing" {
		t.Fatalf("entries %v skipped %v", m.Entries, m.Skipped)
	}
}

func TestBuildSkipsABundleThatPanics(t *testing.T) {
	assets, entries := fakeAssets(t, "text)en)boom", "text)en)ui")
	var read []string
	inner := fakeRebuild(&read)
	m, err := Build(assets, entries, "listmd5", testPack, t.TempDir(), func(raw []byte, name string, values map[string]string) ([]byte, uint32, bool, error) {
		if name == "text)en)boom" {
			panic("index out of range")
		}
		return inner(raw, name, values)
	})
	if err != nil || len(m.Entries) != 1 || strings.Join(m.Skipped, ",") != "text)en)boom" {
		t.Fatalf("%v entries %v skipped %v", err, m, m)
	}
}

func TestBuildIgnoresOtherBundles(t *testing.T) {
	assets, entries := fakeAssets(t, "text)ja)ui", "ui)skill)x", "text)en)ui")
	var read []string
	if _, err := Build(assets, entries, "listmd5", testPack, t.TempDir(), fakeRebuild(&read)); err != nil {
		t.Fatal(err)
	}
	if strings.Join(read, ",") != "text)en)ui" {
		t.Fatalf("read %v", read)
	}
}

func TestLoadManifestNeedsFinishedBuild(t *testing.T) {
	if _, err := LoadManifest(t.TempDir()); err == nil {
		t.Fatal("no error")
	}
}

func TestBuildID(t *testing.T) {
	a := BuildID("p", "l")
	if a != BuildID("p", "l") || len(a) != 16 || a == BuildID("q", "l") || a == BuildID("p", "m") {
		t.Fatalf("%s", a)
	}
}

func TestRealBuild(t *testing.T) {
	dump := dumpRevision(t)
	data, err := os.ReadFile(filepath.Join(dump, "list.bin"))
	if err != nil {
		t.Fatal(err)
	}
	_, entries, err := ParseList(data)
	if err != nil {
		t.Fatal(err)
	}
	pack := &Pack{Language: "pt", Hash: "h", Game: map[string]string{"ui.Outgame.Footer.Quest": "Missões", "gift.comment.3": "Enviado"}}
	out := t.TempDir()
	m, err := Build(dump, entries, "l", pack, out, DefaultRebuilder)
	if err != nil {
		t.Fatal(err)
	}
	var paths []string
	for id, e := range m.Entries {
		paths = append(paths, e.Path)
		file, err := os.ReadFile(filepath.Join(out, id+".assetbundle"))
		sum := md5.Sum(file)
		if err != nil || uint64(len(file)) != e.Size || hex.EncodeToString(sum[:]) != e.MD5 {
			t.Fatalf("%s: file does not match its entry (%v)", e.Path, err)
		}
	}
	sort.Strings(paths)
	if strings.Join(paths, ",") != "text)en)gift,text)en)ui" || len(m.Skipped) != 0 {
		t.Fatalf("built %v skipped %v", paths, m.Skipped)
	}
}
