package mobile

import (
	"log"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Other files are refused by their contents, with a message naming the
// Global and the Japanese master data.
func TestCheckMasterRefusesOtherFiles(t *testing.T) {
	path := filepath.Join(t.TempDir(), "picked")
	os.WriteFile(path, []byte("x"), 0o644)
	for _, name := range []string{"game.db", "backup.zip", "20240404193219.bin", "master.e", ""} {
		got := CheckMaster(path, name)
		if !strings.Contains(got, "20240404193219.bin.e") || !strings.Contains(got, "20240405123139.bin.e") {
			t.Errorf("CheckMaster(%q) = %q, want both master-data files named", name, got)
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
	// A browser names a second download "20240404193219.bin (1).e".
	for _, name := range []string{"20240404193219.bin.e", "20240404193219 (1).BIN.E", "master_20261014.bin.e",
		"20240404193219.bin (1).e", "20240404193219.bin.e.download", ""} {
		if got := CheckMaster(master, name); got != "" {
			t.Errorf("CheckMaster(%q) = %q", name, got)
		}
	}
}

func TestCheckMasterAcceptsTheJapaneseMasterData(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_JP_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_JP_MASTER not set")
	}
	for _, name := range []string{"20240405123139.bin.e", "20240405123139.bin (1).e"} {
		if got := CheckMaster(master, name); got != "" {
			t.Errorf("CheckMaster(%q) = %q", name, got)
		}
	}
}

// A large file picked by mistake (the resource dump's .7z) is refused without
// being read into memory.
func TestCheckMasterRefusesLargeFilesUnread(t *testing.T) {
	path := filepath.Join(t.TempDir(), "resource_dump_android.7z")
	f, _ := os.Create(path)
	f.Truncate(maxMasterSize + 1)
	f.Close()
	var logged strings.Builder
	log.SetOutput(&logged)
	defer log.SetOutput(os.Stderr)
	if got := CheckMaster(path, "resource_dump_android.7z"); !strings.Contains(got, "isn't NieR Re[in]carnation master data") {
		t.Errorf("CheckMaster = %q", got)
	}
	if !strings.Contains(logged.String(), "too large") {
		t.Errorf("refused for another reason: %s", logged.String())
	}
}
