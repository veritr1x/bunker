package translation

import (
	"os"
	"path/filepath"
	"testing"
)

func served(t *testing.T, path string, original uint64, fingerprint string) uint64 {
	t.Helper()
	r, err := ServedRevision(path, original, fingerprint)
	if err != nil {
		t.Fatal(err)
	}
	return r
}

func TestNoStateNoPackServesOriginal(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	if r := served(t, path, 817, "none:x"); r != 817 {
		t.Fatalf("revision %d", r)
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatal("state file created")
	}
}

func TestFirstTranslation(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	if r := served(t, path, 817, "build-a"); r != 1817 {
		t.Fatalf("revision %d", r)
	}
}

func TestSameFingerprintSameRevision(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	if a, b := served(t, path, 817, "build-a"), served(t, path, 817, "build-a"); a != 1817 || b != 1817 {
		t.Fatalf("revisions %d %d", a, b)
	}
}

func TestSwitchingAlwaysGoesUp(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	got := []uint64{served(t, path, 817, "build-a"), served(t, path, 817, "none:x"), served(t, path, 817, "build-a")}
	if got[0] != 1817 || got[1] != 1818 || got[2] != 1819 {
		t.Fatalf("revisions %v", got)
	}
}

func TestOriginalAboveStored(t *testing.T) {
	path := filepath.Join(t.TempDir(), "translation-state.json")
	served(t, path, 817, "build-a")
	if r := served(t, path, 5000, "build-b"); r != 6000 {
		t.Fatalf("revision %d", r)
	}
}
