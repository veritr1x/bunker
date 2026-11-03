package main

import (
	"os"
	"strings"
	"testing"
)

func TestParseWaydroidStatus(t *testing.T) {
	status := parseWaydroidStatus("Session:\tRUNNING\nContainer:\tRUNNING\nVendor type:\tMAINLINE\n" +
		"IP address:\t192.168.240.112\nSession user:\ttester(1000)\nWayland display:\twayland-0\n")
	if status["Session"] != "RUNNING" || status["Session user"] != "tester(1000)" || status["IP address"] != "192.168.240.112" {
		t.Fatalf("status: %v", status)
	}
	if got := parseWaydroidStatus("Session:\tSTOPPED\nVendor type:\tMAINLINE")["Session"]; got != "STOPPED" {
		t.Fatalf("stopped: %q", got)
	}
}

// -emulator keeps Google's emulator on a Linux computer with Waydroid.
func TestEmulatorFlagSkipsWaydroid(t *testing.T) {
	saved := os.Args
	defer func() { os.Args = saved }()
	os.Args = []string{"bunker", "-emulator", "dump.7z"}
	if useWaydroid() {
		t.Fatal("-emulator still uses Waydroid")
	}
}

// The game files reach Waydroid through its root shell, with the script as one argument.
func TestWaydroidRootCommand(t *testing.T) {
	cmd := waydroidPhone{}.rootCommand("tar -xf - -C /data")
	want := []string{"sudo", "waydroid", "shell", "--", "sh", "-c", "tar -xf - -C /data"}
	if len(cmd.Args) != len(want) {
		t.Fatalf("args: %q", cmd.Args)
	}
	for i := range want {
		if cmd.Args[i] != want[i] {
			t.Fatalf("args: %q", cmd.Args)
		}
	}
}

// The game files can arrive before NieR has ever started, when its files
// folder does not exist yet: the folder they create must be NieR's, or the
// Bunker cannot make its saves folder ("permission denied").
func TestInstallScriptGivesTheFilesFolderToNieR(t *testing.T) {
	script := installScript("/s/assets.importing", 10125, 10125, "u:object_r:app_data_file:s0:c125,c256,c512,c768")
	for _, want := range []string{
		"chown 10125:10125 /data/data/" + gamePackage + "/files\n",
		"chown -R 10125:10125 " + serverDir + "\n",
		"chcon u:object_r:app_data_file:s0:c125,c256,c512,c768 /data/data/" + gamePackage + "/files\n",
		"chcon -R u:object_r:app_data_file:s0:c125,c256,c512,c768 " + serverDir + "\n",
	} {
		if !strings.Contains(script, want) {
			t.Errorf("script lacks %q:\n%s", want, script)
		}
	}
}

// Waydroid runs with SELinux off: ls -Z shows "?", and there is no label to set.
func TestInstallScriptWithoutSELinux(t *testing.T) {
	if script := installScript("/s/assets.importing", 10125, 10125, "?"); strings.Contains(script, "chcon") {
		t.Fatalf("chcon without SELinux:\n%s", script)
	}
}
