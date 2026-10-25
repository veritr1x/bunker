//go:build !windows

package main

// The keyboard helper watches the Windows keyboard; elsewhere the emulator's
// own key events are used.
func startKeys(f folders, dev device) bool { return false }

func runKeys(port int, root string) {}
