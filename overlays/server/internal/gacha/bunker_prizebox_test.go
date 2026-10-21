package gacha

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func mamasDream() []masterdata.Prize {
	gem := int32(model.PossessionTypeFreeGem)
	return []masterdata.Prize{
		{Type: gem, Qty: 300000, Stock: 1},
		{Type: gem, Qty: 100, Stock: 3},
		{Type: int32(model.PossessionTypeMaterial), Id: 315001, Qty: 10, Weight: 2}, // unlimited
	}
}

func TestPrizeBoxStockRunsOut(t *testing.T) {
	prizes := mamasDream()
	bs := store.GachaBannerState{}
	got := map[int32]int{}
	for i := 0; i < 400; i++ {
		for _, it := range drawPrizeBox(&bs, prizes, 1) {
			got[it.Count]++
			if it.Count <= 0 {
				t.Fatalf("prize without an amount: %+v", it)
			}
		}
	}
	if got[300000] != 1 || got[100] != 3 {
		t.Fatalf("limited prizes drawn more than their stock: %v", got)
	}
	if got[10] != 396 {
		t.Fatalf("unlimited prize: %v", got)
	}
	if left := PrizesLeft(&bs, prizes); left[0] != 0 || left[1] != 0 || left[2] != -1 {
		t.Fatalf("left: %v", left)
	}
}

func TestPrizeBoxOddsFollowStock(t *testing.T) {
	// Fresh box: weights 1 (jackpot), 3, 2 -> the jackpot comes up about 1 in 6.
	prizes := mamasDream()
	jackpots := 0
	for i := 0; i < 6000; i++ {
		bs := store.GachaBannerState{}
		if drawPrizeBox(&bs, prizes, 1)[0].Count == 300000 {
			jackpots++
		}
	}
	if jackpots < 800 || jackpots > 1200 {
		t.Fatalf("jackpot %d of 6000, want about 1000", jackpots)
	}
}
