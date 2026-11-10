package remotefile

import (
	"bytes"
	"context"
	"crypto/aes"
	"crypto/cipher"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync/atomic"
	"testing"
)

func TestParseLinks(t *testing.T) {
	cases := []struct {
		link, kind, a, b string
	}{
		{"https://archive.org/download/some_item/dump.7z", "archive.org", "some_item", "dump.7z"},
		{"https://archive.org/download/some_item/sub%20dir/dump%201.7z", "archive.org", "some_item", "sub dir/dump 1.7z"},
		{"https://archive.org/details/some_item/dump.7z", "archive.org", "some_item", "dump.7z"},
		{"https://www.archive.org/download/some_item/dump.7z", "archive.org", "some_item", "dump.7z"},
		{"https://drive.google.com/file/d/AbC_d-1/view?usp=sharing", "drive", "AbC_d-1", ""},
		{"https://drive.google.com/open?id=AbC_d-1", "drive", "AbC_d-1", ""},
		{"https://drive.google.com/uc?id=AbC_d-1&export=download", "drive", "AbC_d-1", ""},
		{"https://drive.usercontent.google.com/download?id=AbC_d-1&export=download", "drive", "AbC_d-1", ""},
		{"https://mega.nz/file/H4ndle#K3y_-", "mega", "H4ndle", "K3y_-"},
		{"https://mega.nz/#!H4ndle!K3y_-", "mega", "H4ndle", "K3y_-"},
		{"https://mega.co.nz/#!H4ndle!K3y_-", "mega", "H4ndle", "K3y_-"},
		{"https://example.com/files/dump.7z", "http", "", ""},
		{"https://ia800000.us.archive.org/1/items/some_item/dump.7z", "http", "", ""},
	}
	for _, c := range cases {
		u, _ := url.Parse(c.link)
		kind, a, b := classify(u)
		if kind != c.kind || a != c.a || b != c.b {
			t.Errorf("%s: got %q %q %q, want %q %q %q", c.link, kind, a, b, c.kind, c.a, c.b)
		}
	}
}

func TestMegaFolderRefused(t *testing.T) {
	for _, link := range []string{"https://mega.nz/folder/H4ndle#K3y", "https://mega.nz/#F!H4ndle!K3y"} {
		_, err := Open(context.Background(), link, nil)
		if err == nil || !strings.Contains(err.Error(), "Mega folder links are not supported") {
			t.Errorf("%s: err = %v", link, err)
		}
	}
}

func TestArchiveOrgFallsBackToMirror(t *testing.T) {
	fastRetries(t)
	data := &rangeServer{blob: blob(3 << 20)}
	var broken atomic.Int64
	mux := http.NewServeMux()
	mux.HandleFunc("/download/", func(w http.ResponseWriter, r *http.Request) {
		broken.Add(1)
		w.WriteHeader(http.StatusInternalServerError)
	})
	mux.Handle("/1/items/some_item/", data)
	srv := httptest.NewServer(mux)
	defer srv.Close()
	host := strings.TrimPrefix(srv.URL, "http://")
	mux.HandleFunc("/metadata/some_item", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"d1": host, "d2": host, "dir": "/1/items/some_item",
			"files": []map[string]string{{"name": "dump.7z", "size": fmt.Sprint(len(data.blob))}},
		})
	})
	defer swap(&archiveMetadataURL, srv.URL+"/metadata/")()
	defer swap(&archiveDownloadURL, srv.URL+"/download/")()
	defer swap(&mirrorScheme, "http://")()

	f, err := Open(context.Background(), "https://archive.org/download/some_item/dump.7z", srv.Client())
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if f.Size() != int64(len(data.blob)) || f.Host() != "archive.org" || f.Name() != "dump.7z" {
		t.Fatalf("size %d host %q name %q", f.Size(), f.Host(), f.Name())
	}
	p := make([]byte, 300<<10)
	if _, err := f.ReadAt(p, 1<<20); err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(p, data.blob[1<<20:(1<<20)+len(p)]) {
		t.Fatal("mirror data differs")
	}
	if broken.Load() == 0 {
		t.Fatal("the download URL was never tried")
	}
}

func TestArchiveOrgMissingFile(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"d1":"x","dir":"/1","files":[{"name":"other.7z","size":"5"}]}`))
	}))
	defer srv.Close()
	defer swap(&archiveMetadataURL, srv.URL+"/")()
	_, err := Open(context.Background(), "https://archive.org/download/some_item/dump.7z", srv.Client())
	if err == nil || !strings.Contains(err.Error(), "dump.7z") {
		t.Fatalf("err = %v", err)
	}
}

func TestDriveConfirmPage(t *testing.T) {
	data := &rangeServer{blob: blob(2 << 20)}
	var srv *httptest.Server
	srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()
		if q.Get("id") != "FileId" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		if q.Get("uuid") != "u-123" {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			fmt.Fprintf(w, `<html><body>Google Drive can't scan this file for viruses.
<form id="download-form" action="%s/download" method="get">
<input type="hidden" name="id" value="FileId"><input type="hidden" name="export" value="download">
<input type="hidden" name="confirm" value="t"><input type="hidden" name="uuid" value="u-123">
</form></body></html>`, srv.URL)
			return
		}
		w.Header().Set("Content-Disposition", `attachment; filename="resource dump.7z"`)
		data.ServeHTTP(w, r)
	}))
	defer srv.Close()
	defer swap(&driveDownloadURL, srv.URL+"/download")()
	f, err := Open(context.Background(), "https://drive.google.com/file/d/FileId/view", srv.Client())
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if f.Size() != int64(len(data.blob)) || f.Host() != "drive" || f.Name() != "resource dump.7z" {
		t.Fatalf("size %d host %q name %q", f.Size(), f.Host(), f.Name())
	}
	p := make([]byte, 100<<10)
	if _, err := f.ReadAt(p, 12345); err != nil || !bytes.Equal(p, data.blob[12345:12345+len(p)]) {
		t.Fatalf("read: %v", err)
	}
}

func TestDriveQuota(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.WriteHeader(http.StatusForbidden)
		w.Write([]byte("<html>Too many users have viewed or downloaded this file recently.</html>"))
	}))
	defer srv.Close()
	defer swap(&driveDownloadURL, srv.URL+"/download")()
	_, err := Open(context.Background(), "https://drive.google.com/file/d/FileId/view", srv.Client())
	if err == nil || !strings.Contains(err.Error(), "Google Drive's download limit") {
		t.Fatalf("err = %v", err)
	}
}

// megaServer is a fake Mega API plus a download server holding blob
// encrypted as Mega does.
func megaServer(t *testing.T, plain []byte, quota bool) (link string, srv *httptest.Server) {
	t.Helper()
	key := make([]byte, 32)
	for i := range key {
		key[i] = byte(i*7 + 3)
	}
	aesKey := make([]byte, 16)
	for i := 0; i < 16; i++ {
		aesKey[i] = key[i] ^ key[i+16]
	}
	block, _ := aes.NewCipher(aesKey)
	iv := make([]byte, 16)
	copy(iv, key[16:24])
	enc := make([]byte, len(plain))
	cipher.NewCTR(block, iv).XORKeyStream(enc, plain)
	data := &rangeServer{blob: enc}
	mux := http.NewServeMux()
	srv = httptest.NewServer(mux)
	mux.HandleFunc("/cs", func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		if !strings.Contains(string(body), `"p":"H4ndle"`) || !strings.Contains(string(body), `"a":"g"`) {
			w.Write([]byte("[-9]"))
			return
		}
		fmt.Fprintf(w, `[{"s":%d,"g":"%s/dl/abc"}]`, len(plain), srv.URL)
	})
	mux.HandleFunc("/dl/abc", func(w http.ResponseWriter, r *http.Request) {
		if quota && r.Header.Get("Range") != "bytes=0-0" {
			w.WriteHeader(509)
			return
		}
		data.ServeHTTP(w, r)
	})
	t.Cleanup(srv.Close)
	t.Cleanup(swap(&megaAPIURL, srv.URL+"/cs"))
	return "https://mega.nz/file/H4ndle#" + base64.RawURLEncoding.EncodeToString(key), srv
}

func TestMegaDecryptsAtAnyOffset(t *testing.T) {
	plain := blob(3 << 20)
	link, srv := megaServer(t, plain, false)
	f, err := Open(context.Background(), link, srv.Client())
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if f.Size() != int64(len(plain)) || f.Host() != "mega" {
		t.Fatalf("size %d host %q", f.Size(), f.Host())
	}
	for _, off := range []int64{0, 1, 15, 16, 17, 1<<20 + 3} {
		for _, n := range []int{1, 31, 100 << 10} {
			p := make([]byte, n)
			if _, err := f.ReadAt(p, off); err != nil {
				t.Fatal(err)
			}
			if !bytes.Equal(p, plain[off:off+int64(n)]) {
				t.Fatalf("plaintext differs at %d+%d", off, n)
			}
		}
	}
}

func TestMegaQuota(t *testing.T) {
	fastRetries(t)
	link, srv := megaServer(t, blob(1<<20), true)
	f, err := Open(context.Background(), link, srv.Client())
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	_, err = f.ReadAt(make([]byte, 10), 100)
	if err == nil || !strings.Contains(err.Error(), "Mega's download limit") {
		t.Fatalf("err = %v", err)
	}
}

func swap(v *string, to string) func() {
	old := *v
	*v = to
	return func() { *v = old }
}
