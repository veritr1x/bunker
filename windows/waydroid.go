package main

// Waydroid on Linux: Android runs in a container on the computer itself, so
// there is no emulator to download or boot. Bunker installs bunker.apk with
// waydroid app install and unpacks the game files from the .7z straight into
// the Bunker's own folder in the container, the same way as for the
// emulator: one tar stream, unpacked by Android's tar as root. Waydroid's root
// shell needs sudo, which asks for the player's password once. The game files
// then live in the app's own storage, as on a phone: no shared folder to
// mount after each start.

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// The console's header names where the game runs.
var platformName = "WINDOWS"

// waydroidPhone is the Waydroid container, reached through waydroid shell (as root, through sudo).
type waydroidPhone struct{}

// waydroidAvailable reports whether this computer has Waydroid (Linux only).
func waydroidAvailable() bool {
	_, err := exec.LookPath("waydroid")
	return err == nil
}

func (waydroidPhone) rootCommand(script string) *exec.Cmd {
	// waydroid shell runs COMMAND in the container as root; stdin and stdout pass through.
	return exec.Command("sudo", "waydroid", "shell", "--", "sh", "-c", script)
}

func (w waydroidPhone) shell(command string) (string, error) {
	out, err := w.rootCommand(command).CombinedOutput()
	return strings.TrimSpace(string(out)), err
}

func (w waydroidPhone) stream(script string) *exec.Cmd { return w.rootCommand(script) }

// root makes sure sudo will not stop for a password in the middle of the
// work: it asks once, here, in the console.
func (waydroidPhone) root() error {
	if exec.Command("sudo", "-n", "true").Run() == nil {
		return nil
	}
	ask := exec.Command("sudo", "-v", "-p", "Waydroid's root shell needs your password (sudo): ")
	ask.Stdin, ask.Stdout, ask.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := ask.Run(); err != nil {
		return errors.New("Bunker needs sudo to put the game files into Waydroid. Start it again and enter your password")
	}
	return nil
}

func (waydroidPhone) unroot() {}

// keepAwake keeps Waydroid's container running until stop is closed. Waydroid
// freezes it when no Android app is on screen (its window hidden, the screen
// asleep), which stopped the game files halfway. It also keeps sudo's
// password fresh, so nothing stops to ask for it again.
func keepAwake(stop <-chan struct{}) {
	for {
		exec.Command("sudo", "-n", "-v").Run()
		if waydroidStatus()["Container"] == "FROZEN" {
			exec.Command("sudo", "-n", "waydroid", "container", "unfreeze").Run()
		}
		select {
		case <-stop:
			return
		case <-time.After(3 * time.Second):
		}
	}
}

// waydroidCommand runs waydroid as the player (app install, launch, status).
func waydroidCommand(args ...string) (string, error) {
	out, err := exec.Command("waydroid", args...).CombinedOutput()
	return strings.TrimSpace(string(out)), err
}

// waydroidStatus reads waydroid status: "Session:\tRUNNING" and the like.
func waydroidStatus() map[string]string {
	out, _ := waydroidCommand("status")
	return parseWaydroidStatus(out)
}

func parseWaydroidStatus(out string) map[string]string {
	status := map[string]string{}
	for _, line := range strings.Split(out, "\n") {
		if key, value, ok := strings.Cut(line, ":"); ok {
			status[strings.TrimSpace(key)] = strings.TrimSpace(value)
		}
	}
	return status
}

// waydroidSteps are the steps as the console shows them for Waydroid.
func waydroidSteps(p *panel) *steps {
	platformName, filesTarget = "WAYDROID", "Waydroid"
	return &steps{
		panel:   p,
		adb:     p.add("01 WAYDROID", "WAYDROID"),
		boot:    p.add("01 WAYDROID", "SESSION"),
		install: p.add("02 NIER", "INSTALL"),
		files:   p.add("03 GAME FILES", "UNPACK"),
		open:    p.add("04 DEPLOY", "OPEN"),
	}
}

// startWaydroid starts the Waydroid session when it isn't running, and waits
// until Android has started.
func startWaydroid(s *steps) error {
	version, err := waydroidCommand("--version")
	if err != nil {
		s.set(s.adb, bad, "FAILED", "")
		return fmt.Errorf("waydroid did not run: %s", version)
	}
	s.set(s.adb, good, "READY", version)
	status := waydroidStatus()
	if status["Session"] != "RUNNING" {
		if os.Getenv("WAYLAND_DISPLAY") == "" {
			s.set(s.boot, bad, "STOPPED", "")
			return errors.New("Waydroid is not running. Start Waydroid (open it from your apps menu), then start Bunker again")
		}
		s.set(s.boot, busy, "STARTING", "")
		start := exec.Command("waydroid", "session", "start")
		detach(start)
		if err := start.Start(); err != nil {
			return err
		}
		go start.Wait()
	}
	for deadline := time.Now().Add(3 * time.Minute); ; {
		if status = waydroidStatus(); status["Session"] == "RUNNING" {
			break
		}
		if time.Now().After(deadline) {
			s.set(s.boot, bad, "FAILED", "")
			return errors.New("Waydroid's session did not start. Start Waydroid yourself, then start Bunker again")
		}
		time.Sleep(2 * time.Second)
	}
	s.set(s.boot, good, "RUNNING", status["Session user"])
	return nil
}

// waitAndroid waits until Android in the container has started (as root, after waydroidPhone.root).
func waitAndroid(w waydroidPhone, s *steps) error {
	for deadline := time.Now().Add(3 * time.Minute); ; {
		if out, _ := w.shell("getprop sys.boot_completed"); out == "1" {
			return nil
		}
		if time.Now().After(deadline) {
			s.set(s.boot, bad, "FAILED", "Android did not start")
			return errors.New("Android in Waydroid did not finish starting. Restart Waydroid, then start Bunker again")
		}
		time.Sleep(2 * time.Second)
	}
}

// installWaydroid installs bunker.apk when it is new or has changed.
func installWaydroid(w waydroidPhone, apk string, st *state, s *steps) error {
	s.set(s.install, busy, "CHECKING", "")
	installed, _ := w.shell("pm path " + gamePackage)
	have := strings.HasPrefix(installed, "package:")
	sum, err := fileSHA256(apk)
	if err != nil && !have {
		return errors.New("Bunker needs bunker.apk. Put it next to Bunker, then start again")
	}
	if err != nil || (have && sum == st.APK) {
		s.set(s.install, good, "UP TO DATE", "")
		return nil
	}
	s.set(s.install, busy, "INSTALLING", filepath.Base(apk))
	if out, err := waydroidCommand("app", "install", apk); err != nil {
		return fmt.Errorf("waydroid could not install bunker.apk: %s", out)
	}
	// waydroid app install returns before Android has finished installing.
	for deadline := time.Now().Add(2 * time.Minute); ; {
		if out, _ := w.shell("pm path " + gamePackage); strings.HasPrefix(out, "package:") {
			break
		}
		if time.Now().After(deadline) {
			return errors.New("Android in Waydroid did not install bunker.apk. Install it with waydroid app install bunker.apk to see why")
		}
		time.Sleep(2 * time.Second)
	}
	st.APK = sum
	s.set(s.install, good, "INSTALLED", filepath.Base(apk))
	return nil
}

// runWaydroid does for Waydroid what run does for the emulator.
func runWaydroid(s *steps, root, apk, dump string, st *state, save func()) error {
	if err := startWaydroid(s); err != nil {
		return err
	}
	w := waydroidPhone{}
	if err := w.root(); err != nil {
		return err
	}
	awake := make(chan struct{})
	defer close(awake)
	go keepAwake(awake)
	if err := waitAndroid(w, s); err != nil {
		return err
	}
	if abis, _ := w.shell("getprop ro.product.cpu.abilist"); !strings.Contains(abis, "arm64-v8a") {
		s.set(s.boot, bad, "FAILED", "no ARM64")
		return fmt.Errorf("this Waydroid cannot run ARM64 apps (it supports %q), so the game cannot run on it.\n"+
			"On an Intel or AMD computer, Waydroid needs an ARM translation layer (libndk or libhoudini)", abis)
	}
	if err := installWaydroid(w, apk, st, s); err != nil {
		return err
	}
	save()
	w.shell("pm grant " + gamePackage + " android.permission.POST_NOTIFICATIONS")

	switch {
	case dump != "" && st.GameFiles != archiveID(dump):
		if err := sendGameFiles(w, dump, s); err != nil {
			return err
		}
		st.GameFiles, st.NoGameFiles = archiveID(dump), false
	case st.GameFiles != "":
		s.set(s.files, good, "IN PLACE", strings.Fields(st.GameFiles)[0])
	default:
		s.set(s.files, idle, "SKIPPED", "choose them in the Bunker, or start Bunker with the .7z")
	}
	save()

	s.set(s.open, busy, "OPENING", "")
	if out, err := waydroidCommand("app", "launch", gamePackage); err != nil {
		return fmt.Errorf("could not open NieR: %s", out)
	}
	s.set(s.open, good, "OPEN", "NieR")
	s.say("NieR is open in Waydroid. The next start is quick.")
	return nil
}
