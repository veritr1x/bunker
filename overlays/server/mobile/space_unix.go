//go:build unix

package mobile

import "syscall"

// freeSpace is the space available to this app on dir's file system.
var freeSpace = func(dir string) (int64, error) {
	var st syscall.Statfs_t
	for {
		if e := syscall.Statfs(dir, &st); e == nil {
			return int64(st.Bavail) * int64(st.Bsize), nil
		} else if parent := parentDir(dir); parent != dir {
			dir = parent // the stage may not exist yet
		} else {
			return 0, e
		}
	}
}

func parentDir(dir string) string {
	for i := len(dir) - 1; i > 0; i-- {
		if dir[i] == '/' {
			return dir[:i]
		}
	}
	return "/"
}
