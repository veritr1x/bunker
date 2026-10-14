package gacha

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

func TestDrawRouletteFollowsTheRates(t *testing.T) {
	counts := map[int32]int{}
	for roll := 0; roll < 100000; roll++ {
		counts[DrawRoulette(DefaultRouletteRates, func(int) int { return roll })]++
	}
	want := map[int32]int{10: 60000, 30: 25000, 50: 10000, 100: 4700, 3000: 300}
	for gems, n := range want {
		if counts[gems] != n {
			t.Fatalf("%d gems: %d of 100000 rolls, want %d (%v)", gems, counts[gems], n, counts)
		}
	}
}

func TestRouletteRatesFromPodPrograms(t *testing.T) {
	path := filepath.Join(t.TempDir(), "roulette_rates.json")
	SetRouletteRatesPath(path)
	defer SetRouletteRatesPath("")
	if CurrentRouletteRates() != DefaultRouletteRates {
		t.Fatal("no file should mean the default rates")
	}
	if err := os.WriteFile(path, []byte(`{"percents": [0, 0, 0, 0, 100]}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if got := DrawRoulette(CurrentRouletteRates(), func(n int) int { return n - 1 }); got != 3000 {
		t.Fatalf("saved rates not used: %d", got)
	}
	if err := os.WriteFile(path, []byte(`{"percents": [50, 0, 0, 0, 10]}`), 0o644); err != nil {
		t.Fatal(err)
	}
	future := time.Now().Add(time.Minute)
	os.Chtimes(path, future, future)
	if CurrentRouletteRates() != DefaultRouletteRates {
		t.Fatal("rates not adding up to 100% should fall back to the defaults")
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
