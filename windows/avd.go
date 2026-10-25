package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const avdName = "Bunker"

// avdConfig is the emulated phone: portrait 1080×2400 like the tested emulator,
// with room for the 21 GB of game files. The data partition only takes the space
// it uses. The keyboard is on so the computer's keyboard types into the game.
func avdConfig(abi string, ramMB, cores int) string {
	arch := abi
	if abi == "arm64-v8a" {
		arch = "arm64"
	}
	lines := []string{
		"avd.ini.encoding=UTF-8",
		"PlayStore.enabled=no",
		"abi.type=" + abi,
		"hw.cpu.arch=" + arch,
		fmt.Sprintf("hw.cpu.ncore=%d", cores),
		fmt.Sprintf("hw.ramSize=%d", ramMB),
		"vm.heapSize=512",
		"image.sysdir.1=system-images/android-" + imageAPI + "/google_apis/" + abi + "/",
		"tag.id=google_apis",
		"tag.display=Google APIs",
		"target=android-" + imageAPI,
		"disk.dataPartition.size=64G",
		"sdcard.size=512M",
		"hw.gpu.enabled=yes",
		"hw.gpu.mode=auto",
		"hw.lcd.width=1080",
		"hw.lcd.height=2400",
		"hw.lcd.density=420",
		"hw.initialOrientation=portrait",
		"hw.keyboard=yes",
		"hw.mainKeys=no",
		"hw.audioOutput=yes",
		"hw.audioInput=no",
		"hw.camera.back=none",
		"hw.camera.front=none",
		"showDeviceFrame=no",
		"fastboot.forceColdBoot=no",
	}
	return strings.Join(lines, "\n") + "\n"
}

// writeAVD writes the phone's files into avdHome. They are written on every start,
// so the folder can be moved: the .ini holds the absolute path.
func writeAVD(avdHome, abi string, ramMB, cores int) error {
	dir := filepath.Join(avdHome, avdName+".avd")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	ini := "avd.ini.encoding=UTF-8\npath=" + dir + "\npath.rel=avd/" + avdName + ".avd\ntarget=android-" + imageAPI + "\n"
	if err := writeIfChanged(filepath.Join(avdHome, avdName+".ini"), ini); err != nil {
		return err
	}
	return writeIfChanged(filepath.Join(dir, "config.ini"), avdConfig(abi, ramMB, cores))
}

// writeIfChanged leaves an unchanged file alone, so the emulator's quick boot
// snapshot stays valid.
func writeIfChanged(path, content string) error {
	if old, err := os.ReadFile(path); err == nil && string(old) == content {
		return nil
	}
	return os.WriteFile(path, []byte(content), 0o644)
}
