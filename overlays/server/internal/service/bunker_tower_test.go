package service

import "testing"

// A tower's rewards are claimed once, whichever run (chapter copy) claims them.
func TestTowerRewardsKeyedByTheTower(t *testing.T) {
	for id, want := range map[int32]int32{701: 701, 10000701: 701, 60000705: 705} {
		if got := towerBase(id); got != want {
			t.Fatalf("towerBase(%d) = %d", id, got)
		}
	}
}
