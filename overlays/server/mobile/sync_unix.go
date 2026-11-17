//go:build unix

package mobile

import "syscall"

// syncStorage writes everything buffered through to storage.
func syncStorage() { syscall.Sync() }
