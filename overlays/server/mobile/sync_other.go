//go:build !unix

package mobile

// syncStorage: there is no system-wide sync here; the files are synced as they close.
func syncStorage() {}
