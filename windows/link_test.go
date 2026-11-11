package main

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"bunker/windows/bundleplatform"
	"bunker/windows/remotefile"
)

// The setup program and the Bunker share remotefile; the copies must not drift.
func TestRemotefileCopiesMatch(t *testing.T) {
	mobile := filepath.Join("..", "overlays", "server", "mobile", "remotefile")
	names, _ := filepath.Glob(filepath.Join(mobile, "*.go"))
	mine, _ := filepath.Glob(filepath.Join("remotefile", "*.go"))
	if len(names) == 0 || len(names) != len(mine) {
		t.Fatalf("mobile has %d files, windows/remotefile %d", len(names), len(mine))
	}
	for _, name := range names {
		a, _ := os.ReadFile(name)
		b, err := os.ReadFile(filepath.Join("remotefile", filepath.Base(name)))
		if err != nil || string(a) != string(b) {
			t.Errorf("windows/remotefile/%s differs from %s: copy it over", filepath.Base(name), name)
		}
	}
}

func serve(t *testing.T, path string) string {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { http.ServeFile(w, r, path) }))
	t.Cleanup(srv.Close)
	return srv.URL + "/" + filepath.Base(path)
}

func TestUnpackFromLink(t *testing.T) {
	dest := t.TempDir()
	if err := extractGameFiles(serve(t, "testdata/dump.7z"), dest); err != nil {
		t.Fatal(err)
	}
	got := filesUnder(t, dest)
	if len(got) != len(revisionZero) {
		t.Fatalf("extracted %v", got)
	}
	for name, want := range revisionZero {
		if got[name] != want {
			t.Fatalf("%s = %q, want %q", name, got[name], want)
		}
	}
}

func TestUnpackSpaceRefused(t *testing.T) {
	refuse := errors.New("not enough space")
	var asked int64
	for _, src := range []string{"testdata/dump.7z", serve(t, "testdata/dump.7z")} {
		dest := t.TempDir()
		_, err := unpackGameFiles(src, dirSink(dest), func(total int64) error { asked = total; return refuse }, nil)
		if !errors.Is(err, refuse) {
			t.Fatalf("%s: err = %v", src, err)
		}
		if asked <= 0 {
			t.Fatalf("%s: ready got total %d", src, asked)
		}
		if got := filesUnder(t, dest); len(got) != 0 {
			t.Fatalf("%s: wrote %v before the space check", src, got)
		}
	}
}

func TestPhoneFree(t *testing.T) {
	df := "Filesystem      1K-blocks    Used Available Use% Mounted on\n/dev/block/dm-5   6082364 2930856   3151508  49% /data\n"
	if got := parseFree(df); got != 3151508*1024 {
		t.Fatalf("df: got %d", got)
	}
	if got := parseFree("1000 4096\n"); got != 1000*4096 {
		t.Fatalf("stat: got %d", got)
	}
	if got := parseFree("df: /data: Permission denied"); got != -1 {
		t.Fatalf("unreadable: got %d", got)
	}
	if err := enoughSpace(10, 2_000_000_000); err != nil || enoughSpace(5_000_000_000, 4_000_000_000) == nil || enoughSpace(1, -1) != nil {
		t.Fatal("enoughSpace")
	}
	if e := enoughSpace(20_900_000_000, 3_000_000_000); !strings.Contains(e.Error(), "21.9 GB") || !strings.Contains(e.Error(), "3.0 GB") {
		t.Fatalf("message: %v", e)
	}
}

func TestAskPathAcceptsLinks(t *testing.T) {
	if !isArchiveLink("https://example.com/dump.7z") || isArchiveLink("C:\\dump.7z") {
		t.Fatal("isArchiveLink")
	}
	if archiveID("https://example.com/dump.7z") != "https://example.com/dump.7z" {
		t.Fatalf("archiveID for a link: %q", archiveID("https://example.com/dump.7z"))
	}
}

// A saved link is tried again on the next start only when the network let it
// down; a link that cannot work must not block every start.
func TestForgetBadLink(t *testing.T) {
	stalled := fmt.Errorf("unpacking x: %w", fmt.Errorf("%w for 5m0s: EOF", remotefile.ErrStalled))
	offline := &url.Error{Op: "Get", URL: "https://example.com", Err: &net.OpError{Op: "dial", Err: errors.New("no route")}}
	for _, c := range []struct {
		err  error
		keep bool
	}{
		{stalled, true},
		{offline, true},
		{remotefile.ErrNoRanges, false},
		{errors.New("not enough free space in the phone"), false},
		{errors.New("the link leads to a web page"), false},
	} {
		st := state{GameFilesLink: "https://example.com/d.7z"}
		saved := false
		forgetBadLink(&st, c.err, func() { saved = true })
		if (st.GameFilesLink != "") != c.keep {
			t.Errorf("%v: kept %v, want %v", c.err, st.GameFilesLink != "", c.keep)
		}
		if !c.keep && !saved {
			t.Errorf("%v: state not saved after forgetting the link", c.err)
		}
	}
}

// testBundle is an unmasked, uncompressed UnityFS bundle built for platform.
func testBundle(platform uint32) string {
	var sf bytes.Buffer
	binary.Write(&sf, binary.BigEndian, []uint32{0, 0, 21, 0})
	sf.Write([]byte{0, 0, 0, 0})
	sf.WriteString("2019.4.9f1\x00")
	binary.Write(&sf, binary.LittleEndian, platform)
	sf.Write(make([]byte, 32))
	var info bytes.Buffer
	info.Write(make([]byte, 16))
	binary.Write(&info, binary.BigEndian, []uint32{1, uint32(sf.Len()), uint32(sf.Len())})
	binary.Write(&info, binary.BigEndian, uint16(0))
	binary.Write(&info, binary.BigEndian, uint32(1))
	binary.Write(&info, binary.BigEndian, []uint64{0, uint64(sf.Len())})
	binary.Write(&info, binary.BigEndian, uint32(4))
	info.WriteString("CAB-test\x00")
	var b bytes.Buffer
	b.WriteString("UnityFS\x00")
	binary.Write(&b, binary.BigEndian, uint32(6))
	b.WriteString("5.x.x\x002019.4.9f1\x00")
	binary.Write(&b, binary.BigEndian, uint64(0))
	binary.Write(&b, binary.BigEndian, []uint32{uint32(info.Len()), uint32(info.Len()), 0})
	b.Write(info.Bytes())
	b.Write(sf.Bytes())
	return b.String()
}

// The phone runs the Android client, which cannot load the iOS dump's bundles.
func TestUnpackRefusesIOSDump(t *testing.T) {
	ios := makeZip(t, map[string]string{"revisions/0/list.bin": "\x08\x01", "revisions/0/assetbundle/ui/one.assetbundle": testBundle(bundleplatform.IOS)})
	err := extractGameFiles(ios, t.TempDir())
	if err == nil || !strings.Contains(err.Error(), "for iOS") || !strings.Contains(err.Error(), "resource_dump_android") {
		t.Fatalf("iOS dump: %v", err)
	}
	android := makeZip(t, map[string]string{"revisions/0/list.bin": "\x08\x01", "revisions/0/assetbundle/ui/one.assetbundle": testBundle(bundleplatform.Android)})
	if err := extractGameFiles(android, t.TempDir()); err != nil {
		t.Fatalf("Android dump: %v", err)
	}
}

func TestBundleplatformCopiesMatch(t *testing.T) {
	mobile := filepath.Join("..", "overlays", "server", "mobile", "bundleplatform")
	names, _ := filepath.Glob(filepath.Join(mobile, "*.go"))
	mine, _ := filepath.Glob(filepath.Join("bundleplatform", "*.go"))
	if len(names) == 0 || len(names) != len(mine) {
		t.Fatalf("mobile has %d files, windows/bundleplatform %d", len(names), len(mine))
	}
	for _, name := range names {
		a, _ := os.ReadFile(name)
		b, err := os.ReadFile(filepath.Join("bundleplatform", filepath.Base(name)))
		if err != nil || string(a) != string(b) {
			t.Errorf("windows/bundleplatform/%s differs from %s: copy it over", filepath.Base(name), name)
		}
	}
}
