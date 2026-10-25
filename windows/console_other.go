//go:build !windows

package main

import "os"

// console reports whether the output is a terminal, which redraws in place.
func console(f *os.File) bool {
	st, err := f.Stat()
	return err == nil && st.Mode()&os.ModeCharDevice != 0
}
