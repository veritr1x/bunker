package mobile

import (
	"archive/zip"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func closeLog() {
	logFile.Lock()
	if logFile.f != nil {
		logFile.f.Close()
		logFile.f = nil
	}
	logFile.Unlock()
}

func TestLogFileKeptAcrossSessions(t *testing.T) {
	dir := t.TempDir()
	defer closeLog()
	if e := SetLogDir(dir); e != "" {
		t.Fatal(e)
	}
	log.Print("first session line")
	// A restart reopens the same file and appends.
	if e := SetLogDir(dir); e != "" {
		t.Fatal(e)
	}
	log.Print("second session line")
	data, _ := os.ReadFile(filepath.Join(dir, logName))
	text := string(data)
	if !strings.Contains(text, "first session line") || !strings.Contains(text, "second session line") || strings.Count(text, "=== log opened") != 2 {
		t.Fatalf("log file:\n%s", text)
	}
}

func TestLogFileRotates(t *testing.T) {
	dir := t.TempDir()
	defer closeLog()
	SetLogDir(dir)
	line := strings.Repeat("x", 1023) + "\n"
	for i := 0; i < logLimit/1024+10; i++ {
		fileLog{}.Write([]byte(line))
	}
	fileLog{}.Write([]byte("newest\n"))
	old, e1 := os.Stat(filepath.Join(dir, logName+".1"))
	cur, e2 := os.Stat(filepath.Join(dir, logName))
	if e1 != nil || e2 != nil {
		t.Fatalf("missing log files: %v %v", e1, e2)
	}
	if old.Size() > logLimit || cur.Size() > logLimit || cur.Size() == 0 {
		t.Fatalf("sizes: old %d, current %d", old.Size(), cur.Size())
	}
	data, _ := os.ReadFile(filepath.Join(dir, logName))
	if !strings.HasSuffix(string(data), "newest\n") {
		t.Fatal("newest line not in the current file")
	}
}

func TestExportLogs(t *testing.T) {
	dir := t.TempDir()
	defer closeLog()
	target := filepath.Join(t.TempDir(), "logs.zip")
	if e := ExportLogs(dir, target, "device: test"); !strings.Contains(e, "No server log") {
		t.Fatalf("empty export: %q", e)
	}
	SetLogDir(dir)
	log.Print("exported line")
	os.WriteFile(filepath.Join(dir, logName+".1"), []byte("older\n"), 0600)
	// Written over an existing, longer file through a descriptor, as Android does.
	os.WriteFile(target, []byte(strings.Repeat("junk", 100000)), 0600)
	f, _ := os.OpenFile(target, os.O_RDWR, 0)
	if e := ExportLogsFd(dir, int(f.Fd()), "device: test"); e != "" {
		t.Fatal(e)
	}
	f.Close()
	z, err := zip.OpenReader(target)
	if err != nil {
		t.Fatal(err)
	}
	defer z.Close()
	got := map[string]string{}
	for _, file := range z.File {
		r, _ := file.Open()
		b, _ := io.ReadAll(r)
		r.Close()
		got[file.Name] = string(b)
		if file.Modified.Year() < 2020 {
			t.Fatalf("%s has no real date: %v", file.Name, file.Modified)
		}
	}
	if !strings.Contains(got[logName], "exported line") || got[logName+".1"] != "older\n" || !strings.Contains(got["info.txt"], "device: test") {
		t.Fatalf("archive: %v", got)
	}
}
