package translation

import (
	"os"
	"path/filepath"
	"testing"
)

// served asks for a list as a game that last stored revision requested.
func served(t *testing.T, path string, original, requested uint64, fingerprint string) uint64 {
	t.Helper()
	r, err := ServedRevision(path, original, requested, fingerprint)
	if err != nil {
		t.Fatal(err)
	}
	return r
}

func TestNoStateNoPackServesOriginal(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	if r := served(t, path, 817, 817, "none:x"); r != 817 {
		t.Fatalf("revision %d", r)
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatal("state file created")
	}
}

func TestFirstTranslation(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	if r := served(t, path, 817, 817, "build-a"); r != 1817 {
		t.Fatalf("revision %d", r)
	}
}

func TestSameFingerprintSameRevision(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	if a, b := served(t, path, 817, 817, "build-a"), served(t, path, 817, 1817, "build-a"); a != 1817 || b != 1817 {
		t.Fatalf("revisions %d %d", a, b)
	}
}

func TestSwitchingAlwaysGoesUp(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	got := []uint64{served(t, path, 817, 817, "build-a"), served(t, path, 817, 1817, "none:x"), served(t, path, 817, 1818, "build-a")}
	if got[0] != 1817 || got[1] != 1818 || got[2] != 1819 {
		t.Fatalf("revisions %v", got)
	}
}

func TestOriginalAboveStored(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	served(t, path, 817, 817, "build-a")
	if r := served(t, path, 5000, 1817, "build-b"); r != 6000 {
		t.Fatalf("revision %d", r)
	}
}

func TestUnreadableStateStillGoesUp(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	if err := os.WriteFile(path, nil, 0644); err != nil { // emptied by a power cut
		t.Fatal(err)
	}
	if r := served(t, path, 817, 1817, "build-a"); r != 1818 {
		t.Fatalf("revision %d", r)
	}
}

func TestLostStateGameAhead(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	// the game holds a translated list (1821) but the state file is gone: the originals must go above it
	if r := served(t, path, 821, 1821, "none:x"); r != 1822 {
		t.Fatalf("revision %d", r)
	}
	if _, err := os.Stat(path); err != nil {
		t.Fatal("state not saved")
	}
}

func TestStaleStateBelowGame(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	served(t, path, 817, 817, "build-a")                       // stored 1817 (an old copy of the file)
	if r := served(t, path, 817, 1900, "build-a"); r != 1901 { // the game has seen 1900
		t.Fatalf("revision %d", r)
	}
}
