// Bunker for Windows: runs the Android build of Bunker in Google's Android
// Emulator. On first start it downloads the emulator and an Android 16 image from
// Google (the player accepts Google's license), creates a phone in BunkerData next
// to this program, installs bunker.apk, puts the game files in place and opens
// the game. Later starts only boot the phone and open the game, with no Internet
// connection.
//
// Nothing of the Android SDK or the game is part of this program.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
	"unicode"
)

var version = "dev"

// The game's own package name, which Bunker's build keeps.
const gamePackage = "com.square_enix.android_googleplay.nierspww"

// A private adb server port, so this never restarts the adb of Android Studio or
// other tools with a different adb version.
const adbPort = "5039"

type folders struct {
	root, sdk, home, avd, downloads, logs string
}

func newFolders(root string) folders {
	return folders{
		root:      root,
		sdk:       filepath.Join(root, "sdk"),
		home:      filepath.Join(root, "home"),
		avd:       filepath.Join(root, "home", "avd"),
		downloads: filepath.Join(root, "downloads"),
		logs:      filepath.Join(root, "logs"),
	}
}

func (f folders) env() []string {
	var env []string
	for _, kv := range os.Environ() {
		if !strings.HasPrefix(strings.ToUpper(kv), "ANDROID_") {
			env = append(env, kv)
		}
	}
	return append(env,
		"ANDROID_HOME="+f.sdk, "ANDROID_SDK_ROOT="+f.sdk,
		"ANDROID_USER_HOME="+f.home, "ANDROID_EMULATOR_HOME="+f.home, "ANDROID_AVD_HOME="+f.avd,
		"ANDROID_ADB_SERVER_PORT="+adbPort)
}

func (f folders) adb() string { return filepath.Join(f.sdk, "platform-tools", "adb"+exeSuffix) }
func (f folders) emulator() string {
	return filepath.Join(f.sdk, "emulator", "emulator"+exeSuffix)
}

type state struct {
	APK         string `json:"apk,omitempty"`         // SHA-256 of the bunker.apk last installed
	GameFiles   string `json:"gameFiles,omitempty"`   // name and size of the archive last unpacked into the phone
	NoGameFiles bool   `json:"noGameFiles,omitempty"` // the player chose to import the game files in the Bunker
}

// The steps, as the console shows them.
type steps struct {
	*panel
	adb, emulator, image, accel, boot, install, files, open *row
}

func newSteps(p *panel) *steps {
	return &steps{
		panel:    p,
		adb:      p.add("01 EMULATOR", "ADB"),
		emulator: p.add("01 EMULATOR", "EMULATOR"),
		image:    p.add("01 EMULATOR", "ANDROID 16"),
		accel:    p.add("02 PHONE", "ACCELERATION"),
		boot:     p.add("02 PHONE", "BOOT"),
		install:  p.add("03 NIER", "INSTALL"),
		files:    p.add("04 GAME FILES", "UNPACK"),
		open:     p.add("05 DEPLOY", "OPEN"),
	}
}

func main() {
	p := newPanel(os.Stdout, console(os.Stdout), version)
	s := newSteps(p)
	f, err := run(s)
	// Its own adb server would otherwise keep running and hold files in the
	// folder, which could then not be moved or deleted.
	if f.sdk != "" {
		stop := exec.Command(f.adb(), "kill-server")
		stop.Env = f.env()
		stop.Run()
	}
	if err != nil {
		for _, r := range p.rows {
			if r.tone == busy {
				p.set(r, bad, "FAILED", "")
			}
		}
		p.say("%v\n\nPress Enter to close.", err)
		p.close()
		stdin.ReadString('\n')
		os.Exit(1)
	}
	p.close()
	time.Sleep(8 * time.Second)
}

func run(s *steps) (folders, error) {
	exeDir := "."
	if exe, err := os.Executable(); err == nil {
		if real, err := filepath.EvalSymlinks(exe); err == nil {
			exe = real
		}
		exeDir = filepath.Dir(exe)
	}
	dataDir := flag.String("data", filepath.Join(exeDir, "BunkerData"), "folder for the emulator, the phone and its data")
	apkPath := flag.String("apk", filepath.Join(exeDir, "bunker.apk"), "Bunker's Android build, from the web builder")
	ramMB := flag.Int("ram", 0, "the phone's memory in MB (default: from the computer's memory)")
	flag.Usage = func() {
		fmt.Fprintf(flag.CommandLine.Output(), "Usage: Bunker [options] [resource_dump_android.7z]\n\n"+
			"Drop resource_dump_android.7z on Bunker.exe to add the game files to the phone.\n\n")
		flag.PrintDefaults()
	}
	flag.Parse()

	var f folders
	root, err := filepath.Abs(*dataDir)
	if err != nil {
		return f, err
	}
	f = newFolders(root)
	if !ascii(root) {
		s.say("The emulator may fail to start if the folder path has non-English letters.\n" +
			"If it does, move this folder to a path like C:\\Games\\Bunker.")
	}
	for _, dir := range []string{f.sdk, f.avd, f.downloads, f.logs} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return f, err
		}
	}
	dump := ""
	if flag.NArg() > 0 {
		dump = flag.Arg(0)
	} else {
		dump = findDump(exeDir)
	}
	var st state
	statePath := filepath.Join(root, "state.json")
	if raw, err := os.ReadFile(statePath); err == nil {
		json.Unmarshal(raw, &st)
	}
	save := func() {
		if raw, err := json.MarshalIndent(st, "", " "); err == nil {
			os.WriteFile(statePath, raw, 0o644)
		}
	}

	// Ask for anything missing first, so the rest runs without the player.
	apk := *apkPath
	if _, err := os.Stat(apk); err != nil && st.APK == "" {
		apk = s.askPath("Bunker needs bunker.apk. Build it for Android in the web builder:\n"+
			"https://veritr1x.github.io/bunker/ (you need your own game APK and master data).",
			"Drag bunker.apk into this window and press Enter:")
		if apk == "" {
			return f, errors.New("Bunker needs bunker.apk. Put it next to Bunker.exe, then start again")
		}
	}
	if dump == "" && st.GameFiles == "" && !st.NoGameFiles {
		dump = s.askPath("NieR needs the game files: resource_dump_android.7z (or a .zip of it).\n"+
			"Bunker copies them into the phone. This takes 15 to 20 minutes.",
			"Drag the .7z into this window and press Enter. To skip, just press Enter:")
		st.NoGameFiles = dump == ""
	}

	if err := ensureSDK(f, s); err != nil {
		return f, err
	}
	if *ramMB == 0 {
		*ramMB = phoneMemoryMB(hostMemoryMB())
	}
	if err := writeAVD(f.avd, imageABI(), *ramMB, cores()); err != nil {
		return f, err
	}
	env := f.env()
	avdDir := filepath.Join(f.avd, avdName+".avd")

	var dev device
	for _, serial := range running(f.adb(), env) {
		if d := (device{f.adb(), env, serial}); d.isOurs(avdDir) {
			dev = d
			s.set(s.accel, good, "READY", "")
			s.set(s.boot, good, "RUNNING", serial)
		}
	}
	if dev.serial == "" {
		if dev, err = boot(f, env, s); err != nil {
			return f, err
		}
	}
	if abis, _ := dev.shell("getprop ro.product.cpu.abilist"); !strings.Contains(abis, "arm64-v8a") {
		s.set(s.boot, bad, "FAILED", "no ARM64")
		return f, fmt.Errorf("this Android image cannot run ARM64 apps (it supports %q), so the game cannot run on it", abis)
	}

	if err := install(dev, apk, &st, s); err != nil {
		return f, err
	}
	save()
	// The Lunar Tear notification leads back to the Bunker; grant it instead of
	// asking on the first start.
	dev.shell("pm grant " + gamePackage + " android.permission.POST_NOTIFICATIONS")
	// The game runs full screen; Android's one-time notice about it would cover
	// the game until dismissed.
	dev.shell("settings put secure immersive_mode_confirmations confirmed")

	switch {
	case dump != "" && st.GameFiles != archiveID(dump):
		if err := sendGameFiles(dev, dump, s); err != nil {
			return f, err
		}
		st.GameFiles, st.NoGameFiles = archiveID(dump), false
	case st.GameFiles != "":
		s.set(s.files, good, "IN PLACE", strings.Fields(st.GameFiles)[0])
	default:
		s.set(s.files, idle, "SKIPPED", "choose them in the Bunker, or drop the .7z on Bunker.exe")
	}
	save()

	// Bringing the Bunker over a running game makes the phone start its
	// screens again, which a busy phone may not manage in time.
	if top, _ := dev.shell("dumpsys activity activities | grep -m1 topResumedActivity"); strings.Contains(top, gamePackage+"/com.") {
		s.set(s.open, good, "OPEN", "NieR was already open")
		s.say("NieR is open in the emulator window. To stop, close that window.\n" +
			"The next start is quick. This window closes by itself.")
		return f, nil
	}
	s.set(s.open, busy, "OPENING", "")
	if out, err := dev.shell("monkey -p " + gamePackage + " -c android.intent.category.LAUNCHER 1"); err != nil || strings.Contains(out, "No activities found") {
		return f, fmt.Errorf("could not open NieR: %s", out)
	}
	s.set(s.open, good, "OPEN", "NieR")
	s.say("NieR is open in the emulator window. To stop, close that window.\n" +
		"The next start is quick. This window closes by itself.")
	return f, nil
}

func ascii(s string) bool {
	for _, r := range s {
		if r > unicode.MaxASCII {
			return false
		}
	}
	return true
}

// findDump picks up the game files placed next to the program.
func findDump(dir string) string {
	for _, name := range []string{"resource_dump_android.7z", "resource_dump_android.zip"} {
		if _, err := os.Stat(filepath.Join(dir, name)); err == nil {
			return filepath.Join(dir, name)
		}
	}
	return ""
}

// sdkDir is where a package lives in the SDK folder, as sdkmanager lays it out.
func sdkDir(f folders, pkg string) string {
	return filepath.Join(f.sdk, filepath.FromSlash(strings.ReplaceAll(pkg, ";", "/")))
}

// installedRevision reads a package's version from its source.properties.
func installedRevision(dir string) string {
	raw, err := os.ReadFile(filepath.Join(dir, "source.properties"))
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(raw), "\n") {
		if v, ok := strings.CutPrefix(strings.TrimSpace(line), "Pkg.Revision="); ok {
			return v
		}
	}
	return ""
}

// revision describes an installed package for its row, such as "37.2.12" or
// "x86_64 · r7" for the Android image.
func (s *steps) revision(r *row, dir string) string {
	rev := installedRevision(dir)
	if r == s.image && rev != "" {
		return imageABI() + " · r" + rev
	}
	return rev
}

// ensureSDK downloads what is missing of adb, the emulator and the Android image.
func ensureSDK(f folders, s *steps) error {
	wanted := []struct {
		path, repo string
		row        *row
	}{
		{"platform-tools", toolsRepo, s.adb}, {"emulator", toolsRepo, s.emulator}, {imagePath(), imageRepo, s.image},
	}
	var missing []download
	var rows []*row
	client := &http.Client{}
	repos := map[string]*repository{}
	for _, w := range wanted {
		dir := sdkDir(f, w.path)
		if _, err := os.Stat(dir); err == nil {
			s.set(w.row, good, "READY", s.revision(w.row, dir))
			continue
		}
		s.set(w.row, busy, "CHECKING", "")
		s.say("First start: downloading the Android emulator, adb and an Android 16\n" +
			"image from Google (about 2.3 GB).")
		repo := repos[w.repo]
		if repo == nil {
			var err error
			if repo, err = fetchRepository(client, w.repo); err != nil {
				return fmt.Errorf("could not reach Google's download server: %w\nThe first start needs an Internet connection", err)
			}
			repos[w.repo] = repo
		}
		d, err := repo.pick(w.path, hostOS(), hostArch())
		if err != nil {
			return err
		}
		if err := accept(f, repo, d.License, s); err != nil {
			return err
		}
		s.set(w.row, idle, "QUEUED", fmt.Sprintf("%s · %d MB", d.Revision, d.Size>>20))
		missing = append(missing, d)
		rows = append(rows, w.row)
	}
	for i, d := range missing {
		r := rows[i]
		s.set(r, busy, "DOWNLOADING", "")
		s.say("Downloading %s from Google.\nIf it stops, start Bunker again to resume.", path.Base(d.URL))
		archivePath := filepath.Join(f.downloads, path.Base(d.URL))
		if err := fetch(client, d, archivePath, func(done, total int64) { s.progress(r, done, total, "") }); err != nil {
			return err
		}
		s.set(r, busy, "UNPACKING", "")
		if err := unpack(archivePath, sdkDir(f, d.Path)); err != nil {
			return fmt.Errorf("unpacking %s: %w", d.Path, err)
		}
		os.Remove(archivePath)
		s.set(r, good, "READY", s.revision(r, sdkDir(f, d.Path)))
	}
	if len(missing) > 0 {
		s.say("")
	}
	return nil
}

// accept shows a Google license once and records that the player accepted it.
func accept(f folders, repo *repository, id string, s *steps) error {
	if id == "" {
		return nil
	}
	text, ok := repo.license(id)
	if !ok {
		return fmt.Errorf("Google's repository is missing the license %s", id)
	}
	record := filepath.Join(f.sdk, "licenses", id)
	hash := licenseHash(text)
	if raw, err := os.ReadFile(record); err == nil && strings.Contains(string(raw), hash) {
		return nil
	}
	answer := s.ask("---- Google's license: "+id+" ----\n\n"+text+"\n\n----",
		"Do you accept Google's license above? Type y and press Enter:")
	if a := strings.ToLower(answer); a != "y" && a != "yes" {
		return errors.New("you did not accept Google's license, so nothing was downloaded")
	}
	if err := os.MkdirAll(filepath.Dir(record), 0o755); err != nil {
		return err
	}
	return os.WriteFile(record, []byte("\n"+hash), 0o644)
}

// boot checks for hardware acceleration and starts the phone.
func boot(f folders, env []string, s *steps) (device, error) {
	s.set(s.accel, busy, "CHECKING", "")
	check := exec.Command(f.emulator(), "-accel-check")
	check.Env = env
	out, err := check.CombinedOutput()
	if err != nil {
		s.set(s.accel, bad, "FAILED", "")
		return device{}, fmt.Errorf("the emulator cannot use hardware acceleration:\n%s\n"+
			"To fix it, turn on virtualization (VT-x or SVM) in the BIOS. Then open\n"+
			"\"Turn Windows features on or off\", tick Windows Hypervisor Platform\n"+
			"and restart the computer", strings.TrimSpace(string(out)))
	}
	s.set(s.accel, good, "READY", accelName(string(out)))
	port, err := freePort()
	if err != nil {
		return device{}, err
	}
	logFile, err := os.Create(filepath.Join(f.logs, "emulator.log"))
	if err != nil {
		return device{}, err
	}
	cmd := exec.Command(f.emulator(), "-avd", avdName, "-port", strconv.Itoa(port), "-no-boot-anim")
	cmd.Env, cmd.Stdout, cmd.Stderr = env, logFile, logFile
	detach(cmd)
	s.set(s.boot, busy, "STARTING", "")
	s.say("Starting the phone. The first start takes a few minutes.")
	if err := cmd.Start(); err != nil {
		logFile.Close()
		return device{}, err
	}
	exited := make(chan error, 1)
	go func() { exited <- cmd.Wait(); logFile.Close() }()

	dev := device{f.adb(), env, fmt.Sprintf("emulator-%d", port)}
	if err := dev.waitBoot(10*time.Minute, exited); err != nil {
		return device{}, fmt.Errorf("%w\n%s", err, tail(filepath.Join(f.logs, "emulator.log"), 15))
	}
	s.set(s.boot, good, "RUNNING", dev.serial)
	s.say("")
	return dev, nil
}

// accelName picks the accelerator's name from the emulator's check, such as
// "WHPX(10.0.26300) is installed and usable."
func accelName(out string) string {
	for _, line := range strings.Split(out, "\n") {
		if f := strings.Fields(line); len(f) > 1 && strings.Contains(line, "usable") {
			return strings.SplitN(f[0], "(", 2)[0]
		}
	}
	return ""
}

// freePort finds an emulator console port whose adb port is free too. adb looks
// for emulators on 5554–5585.
func freePort() (int, error) {
	for port := 5554; port <= 5584; port += 2 {
		if portFree(port) && portFree(port+1) {
			return port, nil
		}
	}
	return 0, errors.New("no free emulator port between 5554 and 5585")
}

func portFree(port int) bool {
	l, err := net.Listen("tcp", "127.0.0.1:"+strconv.Itoa(port))
	if err != nil {
		return false
	}
	l.Close()
	return true
}

func tail(path string, lines int) string {
	raw, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	all := strings.Split(strings.TrimSpace(string(raw)), "\n")
	if len(all) > lines {
		all = all[len(all)-lines:]
	}
	return "Last lines of " + path + ":\n" + strings.Join(all, "\n")
}

// install puts bunker.apk on the phone when it is new or has changed.
func install(dev device, apk string, st *state, s *steps) error {
	s.set(s.install, busy, "CHECKING", "")
	installed, _ := dev.shell("pm path " + gamePackage)
	have := strings.HasPrefix(installed, "package:")
	sum, err := fileSHA256(apk)
	if err != nil && !have {
		return errors.New("Bunker needs bunker.apk. Put it next to Bunker.exe, then start again")
	}
	if err != nil || (have && sum == st.APK) {
		// Already installed; a missing bunker.apk is fine then.
		s.set(s.install, good, "UP TO DATE", "")
		return nil
	}
	s.set(s.install, busy, "INSTALLING", filepath.Base(apk))
	if out, err := dev.run("install", "-r", apk); err != nil || !strings.Contains(out, "Success") {
		return installError(out)
	}
	st.APK = sum
	s.set(s.install, good, "INSTALLED", filepath.Base(apk))
	return nil
}

func fileSHA256(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	h := sha256.New()
	if _, err := io.Copy(h, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// phoneMemoryMB sizes the phone's memory from the computer's. The game, the
// Bunker's server and tools and the pages it shows need more than 4 GB together:
// with 4 GB, Android ran out of memory and stopped responding.
func phoneMemoryMB(hostMB int) int {
	switch {
	case hostMB >= 24<<10:
		return 8192
	case hostMB >= 12<<10 || hostMB == 0:
		return 6144
	}
	return 4096
}

// cores gives the phone half the computer's threads, from 4 to 6 (the most the
// emulator allows): the game runs through ARM translation, which needs them.
func cores() int { return max(4, min(6, runtime.NumCPU()/2)) }
