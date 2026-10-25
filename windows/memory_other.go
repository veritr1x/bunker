//go:build !windows && !darwin

package main

import (
	"os"
	"strconv"
	"strings"
)

// hostMemoryMB is the computer's memory in MB, or 0 if unknown.
func hostMemoryMB() int {
	raw, err := os.ReadFile("/proc/meminfo")
	if err != nil {
		return 0
	}
	for _, line := range strings.Split(string(raw), "\n") {
		if f := strings.Fields(line); len(f) >= 2 && f[0] == "MemTotal:" {
			kb, _ := strconv.Atoi(f[1])
			return kb >> 10
		}
	}
	return 0
}
