package main

import (
	"syscall"
	"unsafe"
)

// hostMemoryMB is the computer's memory in MB, or 0 if unknown.
func hostMemoryMB() int {
	var status struct {
		length, load            uint32
		totalPhys, availPhys    uint64
		totalPage, availPage    uint64
		totalVirtual, availVirt uint64
		availExtendedVirtual    uint64
	}
	status.length = uint32(unsafe.Sizeof(status))
	proc := syscall.NewLazyDLL("kernel32.dll").NewProc("GlobalMemoryStatusEx")
	if ok, _, _ := proc.Call(uintptr(unsafe.Pointer(&status))); ok == 0 {
		return 0
	}
	return int(status.totalPhys >> 20)
}
