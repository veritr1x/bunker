package mobile

import (
	"archive/zip"
	"context"
	"fmt"
	"io"
	"io/fs"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
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
	f, e := os.OpenFile(filepath.Join(dir, crashName), os.O_CREATE|os.O_RDWR, 0644)
	if e != nil {
		log.Printf("crash reports off: %v", e)
		return
	}
	defer f.Close() // the runtime keeps its own descriptor
	// The crashing goroutine's trace comes first; the rest can be very long.
	report, _ := io.ReadAll(io.LimitReader(f, crashLimit))
	if len(report) > 0 {
		log.Printf("The previous server run crashed:\n%s", report)
		if e = f.Truncate(0); e == nil {
			_, e = f.Seek(0, io.SeekStart)
		}
		if e != nil {
			log.Printf("could not reset crash log: %v", e)
			return
		}
	}
	if e = debug.SetCrashOutput(f, debug.CrashOptions{}); e != nil {
		log.Printf("crash reports off: %v", e)
	}
}

// ExportLogs writes a zip of the saved logs in dir and the given device
// details to target.
func ExportLogs(dir, target, info string, sources ...LogDirectory) string {
	f, e := os.CreateTemp(filepath.Dir(target), ".bunker-logs-*")
	if e != nil {
		return e.Error()
	}
	defer os.Remove(f.Name())
	if e = writeLogArchive(f, dir, info, sources...); e != nil {
		f.Close()
		return e.Error()
	}
	if e = f.Close(); e != nil {
		return e.Error()
	}
	if e = os.Rename(f.Name(), target); e != nil {
		return e.Error()
	}
	return ""
}

// ExportLogsFd is ExportLogs for a document the caller opened, such as one
// Android's picker created. The caller keeps ownership of fd.
func ExportLogsFd(dir string, fd int, info string, sources ...LogDirectory) string {
	f, e := dupFile(fd, "log export")
	if e != nil {
		return e.Error()
	}
	defer f.Close()
	f.Truncate(0)
	if e = writeLogArchive(f, dir, info, sources...); e != nil {
		return e.Error()
	}
	return ""
}

// LogDirectory names an app-owned diagnostic location inside the ZIP.
// Recurse only in directories dedicated to logs.
type LogDirectory struct {
	Path, Prefix string
	Recursive    bool
}

var logNamePattern = regexp.MustCompile(`(?i)(\.log|[-_]log\.txt)(\.[0-9]+)?(\.gz)?$`)

func archiveLog(z *zip.Writer, source, name string) error {
	f, err := os.Open(source)
	if err != nil {
		return err
	}
	defer f.Close()
	stat, err := f.Stat()
	if err != nil {
		return err
	}
	entry, err := z.CreateHeader(&zip.FileHeader{Name: name, Method: zip.Deflate, Modified: stat.ModTime()})
	if err == nil {
		_, err = io.Copy(entry, io.LimitReader(f, stat.Size()))
	}
	return err
}

func writeLogArchive(w io.Writer, dir, info string, sources ...LogDirectory) error {
	logFile.Lock()
	if logFile.f != nil {
		logFile.f.Sync()
	}
	logFile.Unlock()
	z := zip.NewWriter(w)
	found := false
	for _, source := range append([]LogDirectory{{dir, "", true}}, sources...) {
		if source.Path == "" {
			continue
		}
		err := filepath.WalkDir(source.Path, func(file string, entry fs.DirEntry, err error) error {
			if os.IsNotExist(err) {
				return nil
			}
			if err != nil {
				return err
			}
			if file == source.Path {
				return nil
			}
			if entry.IsDir() && !source.Recursive {
				return filepath.SkipDir
			}
			if !entry.Type().IsRegular() || !logNamePattern.MatchString(entry.Name()) {
				return nil
			}
			stat, err := entry.Info()
			if os.IsNotExist(err) {
				return nil
			}
			if err != nil {
				return err
			}
			if entry.Name() == crashName && stat.Size() == 0 {
				return nil
			}
			rel, err := filepath.Rel(source.Path, file)
			if err != nil {
				return err
			}
			err = archiveLog(z, file, filepath.ToSlash(filepath.Join(source.Prefix, rel)))
			if os.IsNotExist(err) {
				return nil
			}
			if err == nil {
				found = true
			}
			return err
		})
		if err != nil {
			return fmt.Errorf("Cannot export logs: %w", err)
		}
	}
	if runtime.GOOS == "android" {
		// Android keeps Unity and native plugin console messages in logcat.
		// Limit the snapshot to the application's UID, including its game process.
		f, e := os.CreateTemp(dir, ".logcat-*")
		if e == nil {
			defer os.Remove(f.Name())
			ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			cmd := exec.CommandContext(ctx, "/system/bin/logcat", "-d", "--uid="+fmt.Sprint(os.Getuid()), "-v", "threadtime")
			cmd.Stdout = f
			e = cmd.Run()
			cancel()
			stat, statErr := f.Stat()
			f.Close()
			if e == nil && statErr == nil && stat.Size() > 0 {
				if e = archiveLog(z, f.Name(), "android/logcat.log"); e != nil {
					return e
				}
				found = true
			}
		}
	}
	if !found {
		return fmt.Errorf("No server log has been saved yet. Start the server, then try again.")
	}
	part, e := z.CreateHeader(&zip.FileHeader{Name: "info.txt", Method: zip.Deflate, Modified: time.Now()})
	if e != nil {
		return e
	}
	if _, e = fmt.Fprintf(part, "Bunker diagnostic logs\nExported %s\n%s\n", time.Now().Format(time.RFC3339), info); e != nil {
		return e
	}
	return z.Close()
}
