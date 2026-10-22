package mobile

import (
	"archive/zip"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"runtime/debug"
	"sync"
	"time"
)

// The server log is also kept on disk so it survives restarts: server.log,
// moved to server.log.1 once it reaches logLimit, so at most twice that is kept.
// Go writes a fatal crash to stderr, which Android discards, so the runtime also
// writes it to crash.log; the next start moves it into server.log.
const (
	logName    = "server.log"
	logLimit   = 5 << 20
	crashName  = "crash.log"
	crashLimit = 64 << 10
)

var logFile struct {
	sync.Mutex
	dir  string
	f    *os.File
	size int64
}

type fileLog struct{}

func (fileLog) Write(p []byte) (int, error) {
	logFile.Lock()
	defer logFile.Unlock()
	if logFile.f == nil {
		return len(p), nil
	}
	if logFile.size+int64(len(p)) > logLimit {
		logFile.f.Close()
		os.Rename(filepath.Join(logFile.dir, logName), filepath.Join(logFile.dir, logName+".1"))
		if openLog() != nil {
			return len(p), nil
		}
	}
	n, _ := logFile.f.Write(p) // a full disk must not stop the server
	logFile.size += int64(n)
	return len(p), nil
}

func openLog() error {
	// Readable by others so Android's adb can pull it without root; it holds no saves or keys.
	f, e := os.OpenFile(filepath.Join(logFile.dir, logName), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if e != nil {
		logFile.f = nil
		return e
	}
	f.Chmod(0644)
	info, _ := f.Stat()
	logFile.f, logFile.size = f, info.Size()
	return nil
}

// SetLogDir also writes the server log to dir, kept between sessions.
// Returns "" or an error; the in-memory log works either way.
func SetLogDir(dir string) string {
	logFile.Lock()
	if logFile.f != nil {
		logFile.f.Close()
		logFile.f = nil
	}
	logFile.dir = dir
	e := os.MkdirAll(dir, 0755)
	if e == nil {
		e = openLog()
	}
	logFile.Unlock()
	if e != nil {
		return e.Error()
	}
	log.Printf("=== log opened %s ===", time.Now().Format(time.RFC3339))
	keepCrashes(dir)
	return ""
}

// keepCrashes logs the report the previous run left in crash.log, then has the
// runtime write the next fatal error there.
func keepCrashes(dir string) {
	f, e := os.OpenFile(filepath.Join(dir, crashName), os.O_CREATE|os.O_APPEND|os.O_RDWR, 0644)
	if e != nil {
		log.Printf("crash reports off: %v", e)
		return
	}
	defer f.Close() // the runtime keeps its own descriptor
	// The crashing goroutine's trace comes first; the rest can be very long.
	report, _ := io.ReadAll(io.LimitReader(f, crashLimit))
	if len(report) > 0 {
		log.Printf("The previous server run crashed:\n%s", report)
		f.Truncate(0)
	}
	if e = debug.SetCrashOutput(f, debug.CrashOptions{}); e != nil {
		log.Printf("crash reports off: %v", e)
	}
}

// ExportLogs writes a zip of the saved logs in dir and the given device
// details to target.
func ExportLogs(dir, target, info string) string {
	f, e := os.Create(target)
	if e != nil {
		return e.Error()
	}
	if e = writeLogArchive(f, dir, info); e != nil {
		f.Close()
		return e.Error()
	}
	if e = f.Close(); e != nil {
		return e.Error()
	}
	return ""
}

// ExportLogsFd is ExportLogs for a document the caller opened, such as one
// Android's picker created. The caller keeps ownership of fd.
func ExportLogsFd(dir string, fd int, info string) string {
	f, e := dupFile(fd, "log export")
	if e != nil {
		return e.Error()
	}
	defer f.Close()
	f.Truncate(0)
	if e = writeLogArchive(f, dir, info); e != nil {
		return e.Error()
	}
	return ""
}

func writeLogArchive(w io.Writer, dir, info string) error {
	logFile.Lock()
	if logFile.f != nil {
		logFile.f.Sync()
	}
	logFile.Unlock()
	z := zip.NewWriter(w)
	found := false
	for _, name := range []string{logName + ".1", logName, crashName} {
		src, e := os.Open(filepath.Join(dir, name))
		if e != nil {
			continue
		}
		var part io.Writer
		info, e := src.Stat()
		if e == nil && name == crashName && info.Size() == 0 {
			src.Close()
			continue
		}
		if e == nil {
			part, e = z.CreateHeader(&zip.FileHeader{Name: name, Method: zip.Deflate, Modified: info.ModTime()})
		}
		if e == nil {
			_, e = io.Copy(part, src)
		}
		src.Close()
		if e != nil {
			return fmt.Errorf("Cannot export the server log: %w", e)
		}
		found = true
	}
	if !found {
		return fmt.Errorf("No server log has been saved yet. Start the server, then try again.")
	}
	part, e := z.CreateHeader(&zip.FileHeader{Name: "info.txt", Method: zip.Deflate, Modified: time.Now()})
	if e != nil {
		return e
	}
	fmt.Fprintf(part, "Lunar Tear server log\nExported %s\n%s\n", time.Now().Format(time.RFC3339), info)
	return z.Close()
}
