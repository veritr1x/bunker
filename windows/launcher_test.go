package main

import (
	"archive/zip"
	"bytes"
	"crypto/sha1"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// A cut-down copy of Google's repository2-3.xml, in its own layout.
const sampleRepo = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sdk:sdk-repository xmlns:sdk="http://schemas.android.com/sdk/android/repo/repository2/03" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <license id="android-sdk-license" type="text">  Terms and Conditions
  </license>
  <channel id="channel-0">stable</channel>
  <channel id="channel-2">dev</channel>
  <remotePackage path="emulator">
    <revision><major>37</major><minor>3</minor><micro>5</micro></revision>
    <uses-license ref="android-sdk-preview-license"/>
    <channelRef ref="channel-2"/>
    <archives><archive><complete><size>3</size><checksum type="sha1">aa</checksum><url>emulator-windows_x64-dev.zip</url></complete><host-os>windows</host-os><host-arch>x64</host-arch></archive></archives>
  </remotePackage>
  <remotePackage path="emulator">
    <revision><major>36</major><minor>4</minor><micro>9</micro></revision>
    <uses-license ref="android-sdk-license"/>
    <channelRef ref="channel-0"/>
    <archives>
      <archive><complete><size>5</size><checksum type="sha1">BB</checksum><url>emulator-linux_x64-1.zip</url></complete><host-os>linux</host-os><host-arch>x64</host-arch></archive>
      <archive><complete><size>7</size><checksum type="sha1">CC</checksum><url>emulator-windows_x64-1.zip</url></complete><host-os>windows</host-os><host-arch>x64</host-arch></archive>
    </archives>
  </remotePackage>
  <remotePackage path="emulator">
    <revision><major>36</major><minor>1</minor><micro>2</micro></revision>
    <uses-license ref="android-sdk-license"/>
    <channelRef ref="channel-0"/>
    <archives><archive><complete><size>9</size><checksum type="sha1">dd</checksum><url>emulator-windows_x64-0.zip</url></complete><host-os>windows</host-os></archive></archives>
  </remotePackage>
  <remotePackage path="platform-tools">
    <revision><major>37</major><minor>0</minor><micro>1</micro></revision>
    <uses-license ref="android-sdk-license"/>
    <channelRef ref="channel-0"/>
    <archives><archive><complete><size>8</size><checksum type="sha1">ee</checksum><url>https://example.com/platform-tools-win.zip</url></complete><host-os>windows</host-os></archive></archives>
  </remotePackage>
</sdk:sdk-repository>`

func TestPickNewestStableForHost(t *testing.T) {
	repo, err := parseRepository(strings.NewReader(sampleRepo), "https://dl.google.com/android/repository/repository2-3.xml")
	if err != nil {
		t.Fatal(err)
	}
	d, err := repo.pick("emulator", "windows", "x64")
	if err != nil {
		t.Fatal(err)
	}
	if d.Revision.String() != "36.4.9" || d.Size != 7 || d.SHA1 != "cc" || d.License != "android-sdk-license" {
		t.Fatalf("picked %+v", d)
	}
	if d.URL != "https://dl.google.com/android/repository/emulator-windows_x64-1.zip" {
		t.Fatalf("URL %s", d.URL)
	}
	if d, _ := repo.pick("platform-tools", "windows", "x64"); d.URL != "https://example.com/platform-tools-win.zip" {
		t.Fatalf("absolute URL became %s", d.URL)
	}
	if _, err := repo.pick("emulator", "macosx", "aarch64"); err == nil {
		t.Fatal("picked an emulator for a host the list does not have")
	}
	if text, ok := repo.license("android-sdk-license"); !ok || text != "Terms and Conditions" {
		t.Fatalf("license %q", text)
	}
}

func TestLiveImageListHasTheImage(t *testing.T) {
	if os.Getenv("BUNKER_LIVE") == "" {
		t.Skip("set BUNKER_LIVE=1 to read Google's lists")
	}
	for _, c := range []struct{ repo, path, os, arch string }{
		{toolsRepo, "emulator", "windows", "x64"},
		{toolsRepo, "platform-tools", "windows", "x64"},
		{imageRepo, "system-images;android-36;google_apis;x86_64", "windows", "x64"},
	} {
		repo, err := fetchRepository(http.DefaultClient, c.repo)
		if err != nil {
			t.Fatal(err)
		}
		d, err := repo.pick(c.path, c.os, c.arch)
		if err != nil {
			t.Fatal(err)
		}
		if _, ok := repo.license(d.License); !ok {
			t.Fatalf("%s: no license %s", c.path, d.License)
		}
		t.Logf("%s %s %s %d MB", c.path, d.Revision, d.URL, d.Size>>20)
	}
}

func sha1Hex(b []byte) string {
	sum := sha1.Sum(b)
	return hex.EncodeToString(sum[:])
}

func TestFetchResumesAndVerifies(t *testing.T) {
	body := bytes.Repeat([]byte("bunker"), 1000)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.ServeContent(w, r, "a.zip", time0, bytes.NewReader(body))
	}))
	defer srv.Close()
	dir := t.TempDir()
	dest := filepath.Join(dir, "a.zip")
	os.WriteFile(dest+".part", body[:1234], 0o644)
	d := download{URL: srv.URL, Size: int64(len(body)), SHA1: sha1Hex(body)}
	if err := fetch(srv.Client(), d, dest, nil); err != nil {
		t.Fatal(err)
	}
	if got, _ := os.ReadFile(dest); !bytes.Equal(got, body) {
		t.Fatal("resumed download differs")
	}

	bad := filepath.Join(dir, "b.zip")
	d.SHA1 = sha1Hex([]byte("other"))
	if err := fetch(srv.Client(), d, bad, nil); err == nil {
		t.Fatal("accepted a download with the wrong checksum")
	}
	if _, err := os.Stat(bad + ".part"); !os.IsNotExist(err) {
		t.Fatal("kept a download with the wrong checksum")
	}
}

func makeZip(t *testing.T, files map[string]string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "p.zip")
	f, _ := os.Create(path)
	w := zip.NewWriter(f)
	for name, content := range files {
		e, err := w.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		e.Write([]byte(content))
	}
	w.Close()
	f.Close()
	return path
}

func TestUnpackMovesTheArchiveFolder(t *testing.T) {
	archive := makeZip(t, map[string]string{"x86_64/system.img": "img", "x86_64/data/build.prop": "prop"})
	dest := filepath.Join(t.TempDir(), "system-images", "android-36", "google_apis", "x86_64")
	if err := unpack(archive, dest); err != nil {
		t.Fatal(err)
	}
	if got, _ := os.ReadFile(filepath.Join(dest, "data", "build.prop")); string(got) != "prop" {
		t.Fatal("files are not under the package folder")
	}
	if _, err := os.Stat(dest + ".unpack"); !os.IsNotExist(err) {
		t.Fatal("left the unpack folder behind")
	}
}

func TestUnpackRefusesEntriesOutsideTheFolder(t *testing.T) {
	archive := makeZip(t, map[string]string{"emulator/ok": "1", "../evil": "2"})
	dir := t.TempDir()
	if err := unpack(archive, filepath.Join(dir, "emulator")); err == nil {
		t.Fatal("unpacked an entry outside the folder")
	}
	if _, err := os.Stat(filepath.Join(dir, "evil")); !os.IsNotExist(err) {
		t.Fatal("wrote outside the folder")
	}
	if _, err := os.Stat(filepath.Join(dir, "emulator")); !os.IsNotExist(err) {
		t.Fatal("a failed unpack left the package folder")
	}
}

func TestWriteAVD(t *testing.T) {
	home := t.TempDir()
	if err := writeAVD(home, "x86_64", 4096, 4); err != nil {
		t.Fatal(err)
	}
	config, _ := os.ReadFile(filepath.Join(home, "Bunker.avd", "config.ini"))
	for _, want := range []string{"image.sysdir.1=system-images/android-36/google_apis/x86_64/\n", "abi.type=x86_64\n",
		"hw.cpu.arch=x86_64\n", "hw.ramSize=4096\n", "disk.dataPartition.size=64G\n"} {
		if !strings.Contains(string(config), want) {
			t.Errorf("config.ini lacks %q", want)
		}
	}
	ini, _ := os.ReadFile(filepath.Join(home, "Bunker.ini"))
	if !strings.Contains(string(ini), "path="+filepath.Join(home, "Bunker.avd")+"\n") {
		t.Errorf("Bunker.ini: %s", ini)
	}
	if !strings.Contains(avdConfig("arm64-v8a", 4096, 4), "hw.cpu.arch=arm64\n") {
		t.Error("arm64 image has the wrong CPU")
	}

	// An unchanged config is not rewritten, so the quick boot snapshot stays valid.
	path := filepath.Join(home, "Bunker.avd", "config.ini")
	os.Chtimes(path, time0, time0)
	writeAVD(home, "x86_64", 4096, 4)
	if st, _ := os.Stat(path); !st.ModTime().Equal(time0) {
		t.Error("rewrote an unchanged config.ini")
	}
}

func TestInstallErrors(t *testing.T) {
	for out, want := range map[string]string{
		"Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match]": "different signing key",
		"Failure [INSTALL_FAILED_VERSION_DOWNGRADE]":                            "older",
		"Failure [INSTALL_FAILED_NO_MATCHING_ABIS]":                             "ARM64",
		"Failure [something else]":                                              "something else",
	} {
		if err := installError(out); !strings.Contains(err.Error(), want) {
			t.Errorf("%s: %v", out, err)
		}
	}
}

func TestParseDevices(t *testing.T) {
	out := "* daemon started successfully\r\nList of devices attached\r\nemulator-5554\toffline\r\nemulator-5556\tdevice\r\nR5CT\tdevice\r\n\r\n"
	ready, settling := parseDevices(out)
	if len(ready) != 1 || ready[0] != "emulator-5556" || !settling {
		t.Fatalf("ready %v settling %v", ready, settling)
	}
	if _, settling := parseDevices("List of devices attached\nemulator-5554\tdevice\n"); settling {
		t.Fatal("a ready emulator counted as settling")
	}
}

func TestEnvReplacesAndroidVariables(t *testing.T) {
	t.Setenv("ANDROID_HOME", "/elsewhere")
	env := newFolders("/data").env()
	count := 0
	for _, kv := range env {
		if strings.HasPrefix(kv, "ANDROID_HOME=") {
			count++
			if kv != "ANDROID_HOME="+filepath.Join("/data", "sdk") {
				t.Errorf("kept %s", kv)
			}
		}
	}
	if count != 1 {
		t.Errorf("ANDROID_HOME set %d times", count)
	}
}

var time0 = mustTime("2020-01-02T03:04:05Z")

func mustTime(s string) time.Time {
	t, err := time.Parse(time.RFC3339, s)
	if err != nil {
		panic(err)
	}
	return t
}
