package service

import (
	"bytes"
	"crypto/md5"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// newLinkFixture makes a server copy of one asset bundle and an OctoLinks
// whose lookup returns it. It returns the links and the cache entry's path.
func newLinkFixture(t *testing.T, data []byte) (*OctoLinks, string, string) {
	t.Helper()
	root := t.TempDir()
	sum := md5.Sum(data)
	md5Hex := hex.EncodeToString(sum[:])
	server := filepath.Join(root, "server", "assets", "revisions", "0", "assetbundle", "a.assetbundle")
	if err := os.MkdirAll(filepath.Dir(server), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(server, data, 0o644); err != nil {
		t.Fatal(err)
	}
	links := NewOctoLinks(filepath.Join(root, "octo"), filepath.Join(root, "server"), "android")
	links.find = func(objectId, assetType string) []assetCandidate {
		if objectId != "02Vz10" || assetType != "assetbundle" {
			return nil
		}
		return []assetCandidate{{Path: server, Revision: "0", ExpectedMD5: md5Hex}}
	}
	// Cache folder: hex of "A" + object id, in bucket 7 of app 301.
	cached := filepath.Join(root, "octo", "v1", "301", "7", "413032567A3130", md5Hex)
	return links, server, cached
}

func writeCached(t *testing.T, path string, data []byte) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func sameFile(t *testing.T, a, b string) bool {
	t.Helper()
	ai, err := os.Stat(a)
	if err != nil {
		return false
	}
	bi, err := os.Stat(b)
	if err != nil {
		t.Fatal(err)
	}
	return os.SameFile(ai, bi)
}

func TestOctoLinksSweepLinksMatchingFiles(t *testing.T) {
	data := []byte("asset bundle bytes")
	links, server, cached := newLinkFixture(t, data)
	writeCached(t, cached, data)
	other := filepath.Join(filepath.Dir(cached), "00000000000000000000000000000000")
	writeCached(t, other, []byte("not the server's file"))

	links.Sweep()

	if !sameFile(t, cached, server) {
		t.Fatal("cached copy was not linked to the server's file")
	}
	if sameFile(t, other, server) {
		t.Fatal("a file with another md5 was linked")
	}
	if got, _ := os.ReadFile(server); string(got) != string(data) {
		t.Fatalf("server file changed: %q", got)
	}
}

func TestOctoLinksSkipsIncompleteDownload(t *testing.T) {
	data := []byte("asset bundle bytes")
	links, server, cached := newLinkFixture(t, data)
	writeCached(t, cached, data[:5])

	links.Sweep()

	if sameFile(t, cached, server) {
		t.Fatal("a partly written file was linked")
	}
}

func TestOctoLinksUnlinksBeforeServingAgain(t *testing.T) {
	data := []byte("asset bundle bytes")
	links, server, cached := newLinkFixture(t, data)
	writeCached(t, cached, data)
	links.Sweep()
	if !sameFile(t, cached, server) {
		t.Fatal("setup: not linked")
	}

	// The game downloads the file again and rewrites its cache entry in place.
	handler := links.Wrap(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if _, err := os.Stat(cached); !os.IsNotExist(err) {
			t.Error("cache entry still present while the file is served")
		}
		w.Write(data)
	}))
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest("GET", "/resource-bundle-server/unso-300116832-assetbundle/02Vz10", nil))
	f, err := os.OpenFile(cached, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o644)
	if err != nil {
		t.Fatal(err)
	}
	f.Write([]byte("torn"))
	f.Close()
	if got, _ := os.ReadFile(server); string(got) != string(data) {
		t.Fatalf("rewriting the cache entry changed the server's file: %q", got)
	}

	// Once the game has saved the whole download, it is linked again.
	writeCached(t, cached, data)
	deadline := time.Now().Add(20 * time.Second)
	for !sameFile(t, cached, server) {
		if time.Now().After(deadline) {
			t.Fatal("the new download was not linked")
		}
		time.Sleep(50 * time.Millisecond)
	}
}

func TestOctoLinksIgnoresOtherRequests(t *testing.T) {
	links, _, _ := newLinkFixture(t, []byte("x"))
	served := false
	links.Wrap(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { served = true })).
		ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/v2/pub/a/301/v/300116832/list/0", nil))
	if !served {
		t.Fatal("request was not passed on")
	}
}

func TestOctoLinksSymbolicWhenHardLinksRefused(t *testing.T) {
	data := bytes.Repeat([]byte("asset bundle bytes "), 400)
	links, server, cached := newLinkFixture(t, data)
	links.symbolic = true // as on Android, where SELinux refuses hard links
	writeCached(t, cached, data)

	links.Sweep()

	info, err := os.Lstat(cached)
	if err != nil || info.Mode()&os.ModeSymlink == 0 || !sameFile(t, cached, server) {
		t.Fatal("cached copy was not replaced with a symbolic link to the server's file")
	}
	links.Wrap(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write(data) })).
		ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/resource-bundle-server/unso-300116832-assetbundle/02Vz10", nil))
	if err := os.WriteFile(cached, []byte("torn"), 0o644); err != nil {
		t.Fatal(err)
	}
	if got, _ := os.ReadFile(server); string(got) != string(data) {
		t.Fatalf("rewriting the cache entry changed the server's file: %q", got)
	}
}

func TestOctoLinksMovieNames(t *testing.T) {
	if sum, ok := cacheSum("2ea6a4b003245d340a405318ed666970.mp4"); !ok || sum != "2ea6a4b003245d340a405318ed666970" {
		t.Fatalf("movie name: %q %v", sum, ok)
	}
	for _, name := range []string{".meta", "2ea6a4b0.mp4", "2ea6a4b003245d340a405318ed666970.link"[:10]} {
		if _, ok := cacheSum(name); ok {
			t.Fatalf("%q read as a cache file", name)
		}
	}
}

func TestOctoLinksLeavesSmallFilesWhenSymbolic(t *testing.T) {
	data := []byte("small text bundle")
	links, _, cached := newLinkFixture(t, data)
	links.symbolic = true
	writeCached(t, cached, data)

	links.Sweep()

	if info, err := os.Lstat(cached); err != nil || !info.Mode().IsRegular() {
		t.Fatal("a file smaller than a symbolic link was replaced")
	}
}
