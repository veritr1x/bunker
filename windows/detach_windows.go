package main

import (
	"os/exec"
	"syscall"
)

// detach lets the emulator outlive this console window: closing the window would
// otherwise stop it without saving.
func detach(cmd *exec.Cmd) {
	const detachedProcess = 0x00000008
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: detachedProcess | syscall.CREATE_NEW_PROCESS_GROUP}
}

const exeSuffix = ".exe"
