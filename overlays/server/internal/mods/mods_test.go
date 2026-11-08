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

func TestChallengeBonus(t *testing.T) {
	for _, c := range []struct {
		s      Settings
		paused bool
		want   int32
	}{
		{Settings{}, false, 1},
		{Settings{HardEnemies: 2}, false, 3},
		{Settings{HardEnemies: 5, WeaknessOnly: true}, false, 10}, // 6×2, capped at 10
		{Settings{HardEnemies: 1.5, SlowSkills: true}, false, 4},
		{Settings{WeaknessOnly: true, SlowSkills: true}, false, 4},
		{Settings{HardEnemies: 2, StoryFriends: true}, false, 3}, // World mods don't pause it
		{Settings{HardEnemies: 2, FreeSkips: true}, false, 1},    // a comfort mod pauses it
		{Settings{HardEnemies: 2, ExpMultiplier: 2}, false, 1},
		{Settings{HardEnemies: 2, RewardMultiplier: 2}, false, 1},
		{Settings{HardEnemies: 2, ExpMultiplier: 1, RewardMultiplier: 1}, false, 3}, // ×1 is off
		{Settings{HardEnemies: 2}, true, 1},                                         // Start a new day pauses it
	} {
		if got := c.s.ChallengeBonus(c.paused); got != c.want {
			t.Errorf("%+v paused=%v: bonus %d, want %d", c.s, c.paused, got, c.want)
		}
	}
	if got := (Settings{RewardMultiplier: 5, HardEnemies: 2}).RewardFactor(false); got != 5 {
		t.Errorf("with comfort mods the reward factor is the multiplier: %d", got)
	}
	if got := (Settings{HardEnemies: 3}).RewardFactor(false); got != 4 {
		t.Errorf("challenge reward factor %d, want 4", got)
	}
	if got := (Settings{}).RewardFactor(false); got != 1 {
		t.Errorf("no mods: reward factor %d", got)
	}
	if got := (Settings{ExpMultiplier: 3}).ExpFactor(); got != 3 {
		t.Errorf("exp factor %d", got)
	}
	if got := (Settings{}).ExpFactor(); got != 1 {
		t.Errorf("exp factor off %d", got)
	}
}

func TestValidateNewRanges(t *testing.T) {
	for _, bad := range []Settings{{ExpMultiplier: 11}, {ExpMultiplier: -1}, {HardEnemies: 4}, {HardEnemies: 0.5}, {HardEnemies: 6}} {
		if bad.Validate() == nil {
			t.Errorf("%+v accepted", bad)
		}
	}
	for _, ok := range []Settings{{ExpMultiplier: 10}, {HardEnemies: 1.5}, {HardEnemies: 1}, {HardEnemies: 0}, {HardEnemies: 5}} {
		if err := ok.Validate(); err != nil {
			t.Errorf("%+v: %v", ok, err)
		}
	}
}

// A mods.json written before these mods existed keeps its own and turns none
// of the new ones on.
func TestOldSettingsFileKeepsItsMods(t *testing.T) {
	path := filepath.Join(t.TempDir(), "mods.json")
	SetPath(path)
	t.Cleanup(func() { SetPath("") })
	if err := os.WriteFile(path, []byte(`{"staminaFree": true, "rewardMultiplier": 10}`), 0o600); err != nil {
		t.Fatal(err)
	}
	s := Get()
	if !s.StaminaFree || s.Multiplier() != 10 || s.ExpFactor() != 1 || s.HardEnemies != 0 || s.FreeSkips || s.UnlimitedDailyPlays || s.StoryFriends || s.WeaknessOnly || s.SlowSkills {
		t.Fatalf("got %+v", s)
	}
}
