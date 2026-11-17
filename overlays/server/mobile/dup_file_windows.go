package mobile

import (
	"errors"
	"os"

	"golang.org/x/sys/windows"
)

// On Windows os.File.Fd returns a native HANDLE, not a CRT descriptor index.
// The caller retains that handle and must keep it open (and its Go File alive)
// until duplication finishes. No path is reopened and no source handle closed.
// The duplicate references the same native object/file position and access.
// Existing C.int document-FD exports are not a new uintptr_t Windows C ABI.
func dupFile(fd int, name string) (*os.File, error) {
	source := windows.Handle(uintptr(fd))
	// Reject invalid/non-file pseudo handles using the real native error. Do
	// not restrict valid pipes/chars or FILE_TYPE_UNKNOWN with no native error.
	if _, err := windows.GetFileType(source); err != nil {
		return nil, err
	}
	var duplicate windows.Handle
	process := windows.CurrentProcess()
	if err := windows.DuplicateHandle(process, source, process, &duplicate, 0, false, windows.DUPLICATE_SAME_ACCESS); err != nil {
		return nil, err
	}
	f := os.NewFile(uintptr(duplicate), name)
	if f == nil {
		return nil, errors.Join(windows.ERROR_INVALID_HANDLE, windows.CloseHandle(duplicate))
	}
	return f, nil
}
