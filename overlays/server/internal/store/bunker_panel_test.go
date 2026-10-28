package store

import "testing"

// Anecdote panel progress is saved: a change to it makes the save differ, and
// a clone is independent of the original.
func TestPanelMissionsCloneAndCompare(t *testing.T) {
	a := ExtState{}
	a.EnsureMaps()
	a.PanelMissions[8] = PanelMissionState{Progress: map[int32]int64{101: 3}, Claimed: map[int32]bool{}, PageDone: map[int32]int64{}}
	b := a.Clone()
	if !a.Equal(b) {
		t.Fatal("a clone differs")
	}
	b.PanelMissions[8].Progress[101] = 4
	if a.PanelMissions[8].Progress[101] != 3 {
		t.Fatal("the clone shares progress with the original")
	}
	if a.Equal(b) {
		t.Fatal("changed panel progress compares equal")
	}
}
