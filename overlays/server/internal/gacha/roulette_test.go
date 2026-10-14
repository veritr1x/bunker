package gacha

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

func TestDrawRouletteFollowsTheWeights(t *testing.T) {
	counts := map[int32]int{}
	for roll := 0; roll < 1000; roll++ {
		counts[DrawRoulette(func(int) int { return roll })]++
	}
	want := map[int32]int{10: 600, 30: 250, 50: 100, 100: 47, 3000: 3}
	for gems, n := range want {
		if counts[gems] != n {
			t.Fatalf("%d gems: %d of 1000 rolls, want %d (%v)", gems, counts[gems], n, counts)
		}
	}
}

func TestRewardDrawPaysGemsUpToTheDailyLimit(t *testing.T) {
	h := &GachaHandler{Config: &masterdata.GameConfig{RewardGachaDailyMaxCount: 6}}
	user := &store.UserState{}
	var paid int32
	for spin := 0; spin < 6; spin++ {
		gems, err := h.HandleRewardDraw(user, 1)
		if err != nil || len(gems) != 1 {
			t.Fatalf("spin %d: %v %v", spin, gems, err)
		}
		paid += gems[0]
	}
	if user.Gem.FreeGem != paid || paid < 60 {
		t.Fatalf("free gems %d, paid %d", user.Gem.FreeGem, paid)
	}
	if _, err := h.HandleRewardDraw(user, 1); err == nil {
		t.Fatal("a seventh spin was allowed")
	}
}
