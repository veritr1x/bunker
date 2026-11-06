package mods

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

// Mods changes are in use at once in tests.
func init() { Recheck = 0 }

func TestNoFileMeansTheOriginalGame(t *testing.T) {
	SetPath(filepath.Join(t.TempDir(), "mods.json"))
	if got := Get(); got != (Settings{}) || got.Multiplier() != 1 {
		t.Fatalf("got %+v", got)
	}
	SetPath("")
	if got := Get(); got != (Settings{}) {
		t.Fatalf("no path: got %+v", got)
	}
}

func TestReadsTheFileAgainWhenItChanges(t *testing.T) {
	path := filepath.Join(t.TempDir(), "mods.json")
	SetPath(path)
	if err := os.WriteFile(path, []byte(`{"staminaFree": true, "rewardMultiplier": 3}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if s := Get(); !s.StaminaFree || s.Multiplier() != 3 {
		t.Fatalf("got %+v", s)
	}
	if err := os.WriteFile(path, []byte(`{"shopUnlimited": true, "rewardMultiplier": 10}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if s := Get(); s.StaminaFree || !s.ShopUnlimited || s.Multiplier() != 10 {
		t.Fatalf("after the change got %+v", s)
	}
	os.Remove(path)
	if s := Get(); s != (Settings{}) {
		t.Fatalf("after removing the file got %+v", s)
	}
}

func TestInvalidSettingsTurnEveryModOff(t *testing.T) {
	path := filepath.Join(t.TempDir(), "mods.json")
	SetPath(path)
	for _, body := range []string{`{"rewardMultiplier": 11, "staminaFree": true}`, `{not json`} {
		if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
			t.Fatal(err)
		}
		if s := Get(); s != (Settings{}) {
			t.Fatalf("%s: got %+v", body, s)
		}
	}
}

func TestTheFileIsLookedAtOncePerRecheck(t *testing.T) {
	Recheck = time.Hour
	t.Cleanup(func() { Recheck = 0; SetPath("") })
	path := filepath.Join(t.TempDir(), "mods.json")
	SetPath(path)
	if Get().StaminaFree {
		t.Fatal("a mod without the file")
	}
	if err := os.WriteFile(path, []byte(`{"staminaFree": true}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if Get().StaminaFree {
		t.Fatal("the file was read again within Recheck")
	}
	SetPath(path) // a new path (or a restart) reads it at once
	if !Get().StaminaFree {
		t.Fatal("the change was not read after SetPath")
	}
}
