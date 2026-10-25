//go:build !windows

package main

import (
	"os/exec"
	"syscall"
)

// detach lets the emulator outlive the terminal that started it.
func detach(cmd *exec.Cmd) { cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true} }

const exeSuffix = ""
