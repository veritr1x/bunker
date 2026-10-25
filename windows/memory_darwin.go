package main

import "syscall"

// hostMemoryMB is the computer's memory in MB, or 0 if unknown.
func hostMemoryMB() int {
	s, err := syscall.Sysctl("hw.memsize")
	if err != nil || len(s) < 7 {
		return 0
	}
	// macOS returns the 64-bit value as raw bytes, trailing zero bytes trimmed.
	b := append([]byte(s), make([]byte, 8)...)[:8]
	var n uint64
	for i := 7; i >= 0; i-- {
		n = n<<8 | uint64(b[i])
	}
	return int(n >> 20)
}
