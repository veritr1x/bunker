package service

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"lunar-tear/server/internal/gametime"
)

func viewMasterDir(t *testing.T, withView bool) string {
	t.Helper()
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "20240404193219.bin.e"), []byte("loop"), 0o600)
	if withView {
		os.WriteFile(filepath.Join(dir, ViewMasterName), []byte("view"), 0o600)
		later := time.Now().Add(time.Hour)
		os.Chtimes(filepath.Join(dir, ViewMasterName), later, later)
	}
	return filepath.Join(dir, "20240404193219.bin.e")
}

func setOriginalDates(t *testing.T, on bool) {
	t.Helper()
	gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: gametime.Launch + 100*7*24*3600*1000, OriginalDates: on})
	t.Cleanup(func() { gametime.SetCalendar(nil) })
}

// The client downloads the unshifted copy only in the original-dates view,
// and only if it was built.
func TestViewMasterUsedOnlyInOriginalDates(t *testing.T) {
	master := viewMasterDir(t, true)
	setOriginalDates(t, false)
	if viewMasterFile(master) != master {
		t.Fatal("view copy with the setting off")
	}
	setOriginalDates(t, true)
	if viewMasterFile(master) != filepath.Join(filepath.Dir(master), ViewMasterName) {
		t.Fatal("loop master in the view")
	}
	missing := viewMasterDir(t, false)
	if viewMasterFile(missing) != missing {
		t.Fatal("missing view copy not replaced by the loop master")
	}
}

// Switching changes the version, so the client downloads the right file.
func TestVersionChangesWithTheView(t *testing.T) {
	master := viewMasterDir(t, true)
	s := NewDataServiceServerWithMasterPath(nil, nil, master)
	setOriginalDates(t, false)
	off, _ := s.GetLatestMasterDataVersion(nil, nil)
	setOriginalDates(t, true)
	on, _ := s.GetLatestMasterDataVersion(nil, nil)
	if off.LatestMasterDataVersion == on.LatestMasterDataVersion {
		t.Fatalf("same version %s in both modes", on.LatestMasterDataVersion)
	}
}
