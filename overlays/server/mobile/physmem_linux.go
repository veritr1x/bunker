package mobile

import "syscall"

// physicalMemory is the device's memory in bytes, or 0 if unknown (Android, Linux).
var physicalMemory = func() int64 {
	var info syscall.Sysinfo_t
	if syscall.Sysinfo(&info) != nil {
		return 0
	}
	return int64(info.Totalram) * int64(info.Unit)
}
