package store

import (
	"testing"

	"lunar-tear/server/internal/model"
)

func memoirGranter() *PossessionGranter {
	return &PossessionGranter{
		PartsById: map[int32]PartsRef{
			1: {PartsGroupId: 1, RarityType: 10, PartsInitialLotteryId: 1, PartsStatusSubLotteryGroupId: 1},
		},
		PartsSubStatusPool: map[int32][]int32{1: {9}},
		PartsSubStatusDefs: map[int32]PartsStatusSubDef{9: {StatusKindType: 2, StatusCalculationType: 2, StatusChangeInitialValue: 10}},
	}
}

func subStatuses(u *UserState, uuid string) int {
	n := 0
	for k := range u.PartsStatusSubs {
		if k.UserPartsUuid == uuid {
			n++
		}
	}
	return n
}

// The game opens a memoir's menu only when it has a sub-status, so a rank-1
// memoir (no sub-status in the old rule) showed a small preview instead.
func TestNewMemoirHasASubStatus(t *testing.T) {
	g := memoirGranter()
	u := SeedUserState(1, "u", 0, model.DefaultPlatform)
	g.GrantParts(u, 1, 1000)
	for uuid := range u.Parts {
		if n := subStatuses(u, uuid); n != 1 {
			t.Fatalf("rank-1 memoir has %d sub-statuses, want 1", n)
		}
	}
}

func TestMemoirWithoutSubStatusIsRepaired(t *testing.T) {
	g := memoirGranter()
	u := SeedUserState(1, "u", 0, model.DefaultPlatform)
	u.Parts["bare"] = PartsState{UserPartsUuid: "bare", PartsId: 1, Level: 1}
	u.Parts["fine"] = PartsState{UserPartsUuid: "fine", PartsId: 1, Level: 1}
	u.PartsStatusSubs[PartsStatusSubKey{UserPartsUuid: "fine", StatusIndex: 1}] = PartsStatusSubState{UserPartsUuid: "fine", StatusIndex: 1, PartsStatusSubLotteryId: 9}
	if n := g.RepairMemoirSubStatuses(u, 1000); n != 1 {
		t.Fatalf("repaired %d, want 1", n)
	}
	if subStatuses(u, "bare") != 1 || subStatuses(u, "fine") != 1 {
		t.Fatalf("sub-statuses bare=%d fine=%d, want 1 each", subStatuses(u, "bare"), subStatuses(u, "fine"))
	}
	if n := g.RepairMemoirSubStatuses(u, 2000); n != 0 {
		t.Fatalf("repaired %d on the second start", n)
	}
}
