package questflow

import "testing"

func TestPlayerLevelNeverGoesBack(t *testing.T) {
	// Level n needs thresholds[n] exp; levels up to 120 here.
	thresholds := make([]int32, 121)
	for i := range thresholds {
		thresholds[i] = int32(i) * 100
	}
	cases := []struct {
		name              string
		oldLevel, exp     int32
		wantLevel, wantXP int32
	}{
		{"from exp", 1, 450, 4, 450},
		{"past 100", 99, 11500, 115, 11500},
		{"exp past the last level is kept at its", 119, 99999, 120, 12000},
		// A save edited to level 100 without its exp: 40 exp is level 1's
		// worth, but the level stays.
		{"never goes back", 100, 40, 100, 40},
	}
	for _, c := range cases {
		level, xp := playerLevel(c.oldLevel, c.exp, thresholds)
		if level != c.wantLevel || xp != c.wantXP {
			t.Errorf("%s: level %d exp %d, want %d %d", c.name, level, xp, c.wantLevel, c.wantXP)
		}
	}
}
