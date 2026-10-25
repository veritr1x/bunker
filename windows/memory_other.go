//go:build !windows

package main

import (
	"os"
	"strconv"
	"strings"
	"syscall"
)

// hostMemoryMB is the computer's memory in MB, or 0 if unknown.
func hostMemoryMB() int {
	if raw, err := os.ReadFile("/proc/meminfo"); err == nil {
		for _, line := range strings.Split(string(raw), "\n") {
			if f := strings.Fields(line); len(f) >= 2 && f[0] == "MemTotal:" {
				kb, _ := strconv.Atoi(f[1])
				return kb >> 10
			}
		}
	}
	if s, err := syscall.Sysctl("hw.memsize"); err == nil && len(s) >= 7 {
		// macOS returns the 64-bit value as raw bytes, trailing zero bytes trimmed.
		b := append([]byte(s), make([]byte, 8)...)[:8]
		var n uint64
		for i := 7; i >= 0; i-- {
			n = n<<8 | uint64(b[i])
		}
		return int(n >> 20)
	}
	return 0
}
