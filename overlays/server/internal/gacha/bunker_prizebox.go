package gacha

import (
	"math/rand"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// Prize box summons (Mama's Dream): each draw gives one prize. A limited
// prize (gems) has a stock and is drawn by how many are left; an unlimited
// one has a fixed weight and never runs out. The stock is the player's own
// (the original was shared by every player), kept in the summon's banner
// state by prize index.

// drawPrizeBox draws count prizes from bs's box.
func drawPrizeBox(bs *store.GachaBannerState, prizes []masterdata.Prize, count int) []DrawnItem {
	if bs.BoxDrewCounts == nil {
		bs.BoxDrewCounts = map[int32]int32{}
	}
	out := make([]DrawnItem, 0, count)
	for range count {
		total := 0
		for i, p := range prizes {
			total += prizeWeight(bs, i, p)
		}
		if total == 0 {
			break
		}
		roll := rand.Intn(total)
		for i, p := range prizes {
			w := prizeWeight(bs, i, p)
			if roll >= w {
				roll -= w
				continue
			}
			if p.Stock > 0 {
				bs.BoxDrewCounts[int32(i)]++
			}
			out = append(out, DrawnItem{PossessionType: p.Type, PossessionId: p.Id, Count: max(p.Qty, 1)})
			break
		}
	}
	return out
}

func prizeWeight(bs *store.GachaBannerState, i int, p masterdata.Prize) int {
	if p.Stock == 0 {
		return int(p.Weight)
	}
	return int(max(p.Stock-bs.BoxDrewCounts[int32(i)], 0))
}

// PrizesLeft is how many of each prize are left (-1: unlimited).
func PrizesLeft(bs *store.GachaBannerState, prizes []masterdata.Prize) []int32 {
	left := make([]int32, len(prizes))
	for i, p := range prizes {
		left[i] = -1
		if p.Stock > 0 {
			left[i] = max(p.Stock-bs.BoxDrewCounts[int32(i)], 0)
		}
	}
	return left
}
