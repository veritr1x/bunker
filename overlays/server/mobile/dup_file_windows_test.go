package mobile

import (
	"errors"
	"os"
	"runtime"
	"testing"
	"unsafe"

	"golang.org/x/sys/windows"
)

func nativeHandleFlags(handle windows.Handle) (uint32, error) {
	var flags uint32
	proc := windows.NewLazySystemDLL("kernel32.dll").NewProc("GetHandleInformation")
	ok, _, err := proc.Call(uintptr(handle), uintptr(unsafe.Pointer(&flags)))
	if ok == 0 {
		return 0, err
	}
	return flags, nil
}

func TestDupFileWindowsNativeHandleAndInheritance(t *testing.T) {
	f, err := os.CreateTemp(t.TempDir(), "native-handle-")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	source := windows.Handle(f.Fd())
	if err := windows.SetHandleInformation(source, windows.HANDLE_FLAG_INHERIT, windows.HANDLE_FLAG_INHERIT); err != nil {
		t.Fatal(err)
	}
	d, err := dupFile(int(source), "non-inheritable duplicate")
	runtime.KeepAlive(f)
	if err != nil {
		t.Fatal(err)
	}
	defer d.Close()
	originalFlags, err := nativeHandleFlags(source)
	if err != nil {
		t.Fatal(err)
	}
	duplicateFlags, err := nativeHandleFlags(windows.Handle(d.Fd()))
	if err != nil {
		t.Fatal(err)
	}
	if originalFlags&windows.HANDLE_FLAG_INHERIT == 0 || duplicateFlags&windows.HANDLE_FLAG_INHERIT != 0 {
		t.Fatalf("source/duplicate inheritance: %x/%x", originalFlags, duplicateFlags)
	}
	if _, err := windows.GetFileType(windows.Handle(d.Fd())); err != nil {
		t.Fatalf("returned native handle is not live: %v", err)
	}
	for _, invalid := range []int{0, -1, -2} {
		got, err := dupFile(invalid, "invalid or non-file native handle")
		if got != nil {
			got.Close()
			t.Fatal("invalid/non-file handle unexpectedly wrapped")
		}
		if !errors.Is(err, windows.ERROR_INVALID_HANDLE) {
			t.Fatalf("native error for %d: %v", invalid, err)
		}
	}
	read, write, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer read.Close()
	defer write.Close()
	pipe, err := dupFile(int(read.Fd()), "native pipe")
	runtime.KeepAlive(read)
	if err != nil {
		t.Fatal(err)
	}
	defer pipe.Close()
	if _, err := write.Write([]byte("p")); err != nil {
		t.Fatal(err)
	}
	b := make([]byte, 1)
	if _, err := pipe.Read(b); err != nil || string(b) != "p" {
		t.Fatalf("valid pipe must not be rejected: %q %v", b, err)
	}
}
