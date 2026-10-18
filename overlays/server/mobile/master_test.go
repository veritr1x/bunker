package mobile

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCheckMasterRefusesOtherNames(t *testing.T) {
	path := filepath.Join(t.TempDir(), "picked")
	os.WriteFile(path, []byte("x"), 0o644)
	for _, name := range []string{"game.db", "backup.zip", "20240404193219.bin", "master.e", ""} {
		if got := CheckMaster(path, name); !strings.Contains(got, "20240404193219.bin.e") {
			t.Errorf("CheckMaster(%q) = %q, want the choose-the-file message", name, got)
		}
	}
}

func TestCheckMasterRefusesWrongContents(t *testing.T) {
	path := filepath.Join(t.TempDir(), "picked")
	os.WriteFile(path, []byte("renamed text file"), 0o644)
	if got := CheckMaster(path, "20240404193219.bin.e"); !strings.Contains(got, "isn't NieR Re[in]carnation master data") {
		t.Errorf("CheckMaster = %q", got)
	}
}

func TestCheckMasterAcceptsTheMasterData(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	for _, name := range []string{"20240404193219.bin.e", "20240404193219 (1).BIN.E", "master_20261014.bin.e"} {
		if got := CheckMaster(master, name); got != "" {
			t.Errorf("CheckMaster(%q) = %q", name, got)
		}
	}
}
