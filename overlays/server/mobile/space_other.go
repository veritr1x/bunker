//go:build !unix

package mobile

import "errors"

var freeSpace = func(string) (int64, error) { return 0, errors.New("free space unknown") }
