package main

import (
	"bufio"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// The Bunker's game files in the phone (FilesStore.java): assets/revisions/0
// and assets/release/<master data>, under the app's private files.
const (
	serverDir  = "/data/data/" + gamePackage + "/files/server"
	masterData = "20240404193219.bin.e"
)

// archiveID names an archive by file name and size, to tell whether it was sent.
func archiveID(dump string) string {
	info, err := os.Stat(dump)
	if err != nil {
		return ""
	}
	return fmt.Sprintf("%s %d", filepath.Base(dump), info.Size())
}

// sendGameFiles unpacks revision 0 of the archive on the computer and streams
// it into the Bunker's own game files, as one tar the phone's tar unpacks.
// Nothing is written to the computer's disk, and the phone's shared storage,
// which is several times slower, is not used. The Bunker then has its game
// files without importing anything.
//
// The Bunker's files are private to it, so this uses adb as root, which the
// emulator's Google APIs image allows, and does what the Bunker's import does
// when it installs files (FilesStore.install): it keeps the master data and the
// calendar's next loop, and swaps the new files in only once they are complete.
func sendGameFiles(dev device, dump string, s *steps) error {
	s.set(s.files, busy, "PREPARING", "")
	if err := dev.root(); err != nil {
		return err
	}
	defer dev.unroot()
	// The Bunker and its server must not be using the files while they change.
	dev.shell("am force-stop " + gamePackage)
	owner, err := dev.shell("stat -c '%u %g' /data/data/" + gamePackage)
	ids := strings.Fields(owner)
	if err != nil || len(ids) != 2 {
		return fmt.Errorf("NieR is not installed in the phone: %s", owner)
	}
	uid, _ := strconv.Atoi(ids[0])
	gid, _ := strconv.Atoi(ids[1])
	label, err := dev.shell("ls -Zd /data/data/" + gamePackage)
	if f := strings.Fields(label); err == nil && len(f) == 2 {
		label = f[0]
	} else {
		return fmt.Errorf("cannot read NieR's files in the phone: %s", label)
	}

	stage := serverDir + "/assets.importing"
	cmd := dev.command("exec-in", "rm -rf "+stage+" && mkdir -p "+stage+" && tar -xf - -C "+stage)
	pipe, err := cmd.StdinPipe()
	if err != nil {
		return err
	}
	if err := cmd.Start(); err != nil {
		return err
	}
	buffered := bufio.NewWriterSize(pipe, 4<<20)
	stream := newTarSink(buffered, uid, gid)
	s.set(s.files, busy, "STREAMING", "")
	s.say("Copying the game files from %s into the phone (21 GB).\n"+
		"Keep this window open.", filepath.Base(dump))
	count, err := unpackGameFiles(dump, stream, func(done, total int64) { s.progress(s.files, done, total, "") })
	if err == nil {
		err = stream.close()
	}
	if err == nil {
		err = buffered.Flush()
	}
	pipe.Close()
	if werr := cmd.Wait(); err == nil && werr != nil {
		err = fmt.Errorf("the phone stopped receiving the game files: %w", werr)
	}
	if err != nil {
		dev.shell("rm -rf " + stage)
		return err
	}

	// adb exec-in does not report the phone's exit status, so the result is checked.
	s.set(s.files, busy, "CHECKING", fmt.Sprintf("%d files", count))
	got, _ := dev.shell("find " + stage + "/revisions/0 -type f | wc -l")
	if strings.TrimSpace(got) != strconv.FormatInt(count, 10) {
		dev.shell("rm -rf " + stage)
		return fmt.Errorf("only %s of %d game files reached the phone. Start Bunker again to retry", strings.TrimSpace(got), count)
	}
	assets, previous := serverDir+"/assets", serverDir+"/assets.previous"
	script := strings.Join([]string{
		"set -e",
		"mkdir -p " + stage + "/release",
		keep(assets+"/release/"+masterData, stage+"/release/"+masterData),
		keep(assets+"/release/calendar-next.bin", stage+"/release/calendar-next.bin"),
		"rm -rf " + previous,
		"if [ -e " + assets + " ]; then mv " + assets + " " + previous + "; fi",
		"mv " + stage + " " + assets,
		"rm -rf " + previous,
		fmt.Sprintf("chown -R %d:%d %s", uid, gid, serverDir),
		"chcon -R " + label + " " + serverDir,
		"echo installed",
	}, "\n")
	s.set(s.files, busy, "INSTALLING", "")
	if out, err := dev.shell(script); err != nil || !strings.HasSuffix(out, "installed") {
		return fmt.Errorf("could not install the game files in the phone: %s", out)
	}
	s.set(s.files, good, "IN PLACE", fmt.Sprintf("%d files from %s", count, filepath.Base(dump)))
	s.say("")
	return nil
}

// keep copies a file the Bunker already has into the new files, unless they
// bring their own.
func keep(from, to string) string {
	return "if [ -f " + from + " ] && [ ! -e " + to + " ]; then cp -p " + from + " " + to + "; fi"
}

// root restarts adb in the phone as root.
func (d device) root() error {
	out, err := d.run("root")
	if err != nil || strings.Contains(out, "cannot run as root") {
		return fmt.Errorf("adb cannot get root access in this phone (%s), so it cannot add the game files", out)
	}
	return d.waitUID("0")
}

func (d device) unroot() {
	d.run("unroot")
	d.waitUID("2000")
}

// waitUID waits for adb to come back after restarting as another user.
func (d device) waitUID(want string) error {
	for i := 0; i < 30; i++ {
		d.run("wait-for-device")
		if out, err := d.shell("id -u"); err == nil && out == want {
			return nil
		}
		time.Sleep(time.Second)
	}
	return errors.New("adb did not reconnect after restarting")
}
