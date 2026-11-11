//go:build !linux && !darwin

package mobile

var physicalMemory = func() int64 { return 0 }
