package mobile

import (
	"encoding/binary"
	"syscall"
)

// physicalMemory is the device's memory in bytes, or 0 if unknown (iOS, macOS).
var physicalMemory = func() int64 {
	raw, err := syscall.Sysctl("hw.memsize")
	if err != nil {
		return 0
	}
	b := []byte(raw)
	for len(b) < 8 { // Sysctl drops a trailing zero byte
		b = append(b, 0)
	}
	return int64(binary.LittleEndian.Uint64(b[:8]))
}
