package main

import (
	"os"
	"syscall"
)

// console turns on the console's colours and in-place redrawing, available
// since Windows 10, and UTF-8 for the box characters. It reports false when the
// output is not a console, or the console is too old.
func console(f *os.File) bool {
	var mode uint32
	h := syscall.Handle(f.Fd())
	if syscall.GetConsoleMode(h, &mode) != nil {
		return false
	}
	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	const virtualTerminal = 0x0004
	if ok, _, _ := kernel32.NewProc("SetConsoleMode").Call(uintptr(h), uintptr(mode|virtualTerminal)); ok == 0 {
		return false
	}
	kernel32.NewProc("SetConsoleOutputCP").Call(65001)
	return true
}
