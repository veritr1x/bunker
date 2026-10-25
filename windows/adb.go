package main

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

// device runs adb against one emulator.
type device struct {
	adb    string
	env    []string
	serial string
}

func (d device) command(args ...string) *exec.Cmd {
	cmd := exec.Command(d.adb, append([]string{"-s", d.serial}, args...)...)
	cmd.Env = d.env
	return cmd
}

func (d device) run(args ...string) (string, error) {
	var out bytes.Buffer
	cmd := d.command(args...)
	cmd.Stdout, cmd.Stderr = &out, &out
	err := cmd.Run()
	text := strings.TrimSpace(strings.ReplaceAll(out.String(), "\r\n", "\n"))
	if err != nil {
		return text, fmt.Errorf("adb %s: %v: %s", strings.Join(args, " "), err, text)
	}
	return text, nil
}

func (d device) shell(command string) (string, error) { return d.run("shell", command) }

// waitBoot waits until Android has finished starting, or the emulator stops.
func (d device) waitBoot(timeout time.Duration, exited <-chan error) error {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		select {
		case err := <-exited:
			return fmt.Errorf("the emulator stopped while starting (%v)", err)
		default:
		}
		if out, err := d.shell("getprop sys.boot_completed"); err == nil && out == "1" {
			return nil
		}
		time.Sleep(2 * time.Second)
	}
	return errors.New("Android took too long to start")
}

// running lists the serials of the emulators adb sees.
// A freshly started adb server lists running emulators as offline for a few
// seconds, so this waits for them to settle rather than miss our phone and
// start it a second time.
func running(adb string, env []string) []string {
	var serials []string
	for try := 0; try < 15; try++ {
		cmd := exec.Command(adb, "devices")
		cmd.Env = env
		out, err := cmd.Output()
		if err != nil {
			return nil
		}
		var settling bool
		serials, settling = parseDevices(string(out))
		if !settling {
			break
		}
		time.Sleep(time.Second)
	}
	return serials
}

// parseDevices returns the emulators ready for commands, and whether any is
// still connecting.
func parseDevices(out string) (ready []string, settling bool) {
	for _, line := range strings.Split(out, "\n") {
		f := strings.Fields(line)
		if len(f) != 2 || !strings.HasPrefix(f[0], "emulator-") {
			continue
		}
		if f[1] == "device" {
			ready = append(ready, f[0])
		} else {
			settling = true
		}
	}
	return ready, settling
}

// isOurs tells our emulator apart from any other the player runs.
func (d device) isOurs(avdDir string) bool {
	if out, err := d.run("emu", "avd", "path"); err == nil && !strings.HasPrefix(out, "KO") {
		first := strings.TrimSpace(strings.SplitN(out, "\n", 2)[0])
		return sameFile(first, avdDir)
	}
	out, err := d.run("emu", "avd", "name")
	return err == nil && strings.TrimSpace(strings.SplitN(out, "\n", 2)[0]) == avdName
}

func sameFile(a, b string) bool {
	sa, err1 := os.Stat(a)
	sb, err2 := os.Stat(b)
	return err1 == nil && err2 == nil && os.SameFile(sa, sb)
}

// installError explains the install failures a player can do something about.
func installError(out string) error {
	switch {
	case strings.Contains(out, "INSTALL_FAILED_UPDATE_INCOMPATIBLE"):
		return errors.New("bunker.apk has a different signing key than the NieR in the phone.\n" +
			"Use a bunker.apk signed with the same key (all web builds use the same public key).\n" +
			"Bunker will not uninstall the old one, because that would delete the save")
	case strings.Contains(out, "INSTALL_FAILED_VERSION_DOWNGRADE"):
		return errors.New("bunker.apk is older than the NieR in the phone (NieR may have updated itself).\n" +
			"Use a newer bunker.apk, or remove the old one from this folder")
	case strings.Contains(out, "INSTALL_FAILED_NO_MATCHING_ABIS"):
		return errors.New("this emulator cannot run ARM64 apps")
	case strings.Contains(out, "INSUFFICIENT_STORAGE"):
		return errors.New("the emulator is out of space")
	}
	return fmt.Errorf("installing bunker.apk failed: %s", out)
}
