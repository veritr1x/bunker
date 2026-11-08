package questflow

import (
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
)

// chapterMemoirDrop is what a clear of an event quest adds from the memoirs
// its chapter shows but no quest drops (masterdata.ChapterMemoirs): one time in
// two, one of them at random. Each roll then picks the rank as usual. The
// chance is an estimate; the live game's enemy drop rates are not in the data.
// rate applies the quest's drop-rate campaign; roll(n) is in [0, n).
func chapterMemoirDrop(memoirs []int32, rate func(int32) int32, roll func(int64) int64) []RewardGrant {
	if len(memoirs) == 0 || roll(2) != 0 {
		return nil
	}
	id := memoirs[roll(int64(len(memoirs)))]
	return []RewardGrant{{PossessionType: model.PossessionTypeParts, PossessionId: id, Count: rate(1)}}
}

func chapterMemoirDrops(questId int32, rate func(int32) int32) []RewardGrant {
	return chapterMemoirDrop(masterdata.ChapterMemoirs()[questId], rate, randInt64n)
}
