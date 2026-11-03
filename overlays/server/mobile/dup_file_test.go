package mobile

import (
	"archive/zip"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestDupFileExportLogsCallerOwnership(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, logName), []byte("actual saved log\n"), 0600); err != nil {
		t.Fatal(err)
	}
	target, err := os.CreateTemp(t.TempDir(), "logs-*.zip")
	if err != nil {
		t.Fatal(err)
	}
	defer target.Close()
	if err := ExportLogsFd(dir, int(target.Fd()), "dup ownership fixture"); err != "" {
		t.Fatal(err)
	}
	runtime.KeepAlive(target)
	info, err := target.Stat()
	if err != nil {
		t.Fatalf("export closed caller handle: %v", err)
	}
	z, err := zip.NewReader(target, info.Size())
	if err != nil {
		t.Fatal(err)
	}
	contents := make(map[string]string)
	for _, entry := range z.File {
		r, err := entry.Open()
		if err != nil {
			t.Fatal(err)
		}
		data, err := io.ReadAll(r)
		r.Close()
		if err != nil {
			t.Fatal(err)
		}
		contents[entry.Name] = string(data)
	}
	if contents[logName] != "actual saved log\n" || !strings.Contains(contents["info.txt"], "dup ownership fixture") {
		t.Fatalf("exported contents: %v", contents)
	}
}

func TestDupFileOwnershipAndSharedOffset(t *testing.T) {
	path := filepath.Join(t.TempDir(), "source.bin")
	if err := os.WriteFile(path, []byte("0123456789"), 0600); err != nil {
		t.Fatal(err)
	}
	for _, closeSourceFirst := range []bool{false, true} {
		source, err := os.Open(path)
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { source.Close() })
		if _, err := source.Seek(2, io.SeekStart); err != nil {
			t.Fatal(err)
		}
		duplicate, err := dupFile(int(source.Fd()), "borrowed source")
		runtime.KeepAlive(source)
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { duplicate.Close() })
		if source.Fd() == duplicate.Fd() {
			t.Fatal("duplicate must have independent native handle/descriptor identity")
		}
		b := make([]byte, 2)
		if n, err := duplicate.Read(b); err != nil || n != 2 || string(b) != "23" {
			t.Fatalf("duplicate read: %q %d %v", b, n, err)
		}
		if pos, err := source.Seek(0, io.SeekCurrent); err != nil || pos != 4 {
			t.Fatalf("source did not observe shared offset: %d %v", pos, err)
		}
		if n, err := source.Read(b); err != nil || n != 2 || string(b) != "45" {
			t.Fatalf("source read: %q %d %v", b, n, err)
		}
		if pos, err := duplicate.Seek(0, io.SeekCurrent); err != nil || pos != 6 {
			t.Fatalf("duplicate did not observe shared offset: %d %v", pos, err)
		}
		if _, err := duplicate.ReadAt(b, 0); err != nil || string(b) != "01" {
			t.Fatalf("ReadAt: %q %v", b, err)
		}
		if pos, err := source.Seek(0, io.SeekCurrent); err != nil || pos != 6 {
			t.Fatalf("ReadAt changed shared sequential offset: %d %v", pos, err)
		}
		if _, err := duplicate.Write([]byte("x")); err == nil {
			t.Fatal("read-only source must not gain write access")
		}
		if closeSourceFirst {
			if err := source.Close(); err != nil {
				t.Fatal(err)
			}
			if _, err := duplicate.Seek(0, io.SeekStart); err != nil {
				t.Fatal(err)
			}
			if _, err := duplicate.Read(b); err != nil || string(b) != "01" {
				t.Fatalf("duplicate survives source close: %q %v", b, err)
			}
		} else {
			if err := duplicate.Close(); err != nil {
				t.Fatal(err)
			}
			if _, err := source.Read(b); err != nil || string(b) != "67" {
				t.Fatalf("source survives duplicate close: %q %v", b, err)
			}
		}
	}
}

func TestDupFileReadWriteAndInvalid(t *testing.T) {
	f, err := os.CreateTemp(t.TempDir(), "writable-")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	d, err := dupFile(int(f.Fd()), "writable")
	runtime.KeepAlive(f)
	if err != nil {
		t.Fatal(err)
	}
	defer d.Close()
	if _, err := d.Write([]byte("native duplicate")); err != nil {
		t.Fatal(err)
	}
	if _, err := f.Seek(0, io.SeekStart); err != nil {
		t.Fatal(err)
	}
	if b, err := io.ReadAll(f); err != nil || string(b) != "native duplicate" {
		t.Fatalf("shared real contents: %q %v", b, err)
	}
	if invalid, err := dupFile(-1, "invalid"); err == nil || invalid != nil {
		if invalid != nil {
			invalid.Close()
		}
		t.Fatalf("invalid descriptor/handle must fail: %v", err)
	}
}
