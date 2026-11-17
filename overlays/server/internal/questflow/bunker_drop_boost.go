package questflow

import (
	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// A drop boost ("drop rate +X") as Bunker applies it. Bunker always grants
// the drops a quest screen shows, so a boost raises each targeted drop's
// expected count by X instead: a rolled 1-in-N drop hits (1 + X) times as
// often (boostedHit), and every other drop gets X more of its count, the
// fraction as a chance of one more (boostCounts).
//
// Sources: Drop Rate+ important items (m_important_item_effect_drop_rate) and
// costume collection bonuses on the main story (bunker_collection_bonus.go).

// dropBoost is the boost in permil for one drop; nil means none.
type dropBoost func(t model.PossessionType, id int32) int64

func (b dropBoost) of(t model.PossessionType, id int32) int64 {
	if b == nil {
		return 0
	}
	return b(t, id)
}

// boostedHit rolls a 1-in-oneIn drop raised by permil. Without a boost it is
// roll(oneIn) == 0, as before; a boost that makes it certain rolls nothing.
func boostedHit(oneIn, permil int64, roll func(int64) int64) bool {
	if permil <= 0 {
		return roll(oneIn) == 0
	}
	if 1000+permil >= oneIn*1000 {
		return true
	}
	return roll(oneIn*1000) < 1000+permil
}

// boostCounts gives each drop count*permil/1000 more, the fraction as a
// chance of one more.
func boostCounts(drops []RewardGrant, boost dropBoost, roll func(int64) int64) []RewardGrant {
	for i := range drops {
		permil := boost.of(drops[i].PossessionType, drops[i].PossessionId)
		if permil <= 0 || drops[i].Count <= 0 {
			continue
		}
		extra := int64(drops[i].Count) * permil
		add := extra / 1000
		if frac := extra % 1000; frac > 0 && roll(1000) < frac {
			add++
		}
		drops[i].Count += int32(add)
	}
	return drops
}

// dropBoostFor is the boost a clear of quest t gets now: the Drop Rate+
// items the player owns that target it, the largest rate of each grouping
// (Drop Rate+ and ++ share one), the groupings added up; on a main quest also
// the costume collection drop rate, on every drop. nil when none apply.
func (h *QuestHandler) dropBoostFor(user *store.UserState, t campaign.QuestTarget, nowMillis int64) dropBoost {
	var collection int64
	if t.QuestType == campaign.QuestTypeMainQuest {
		chapter := mainQuestChapterOf(t.QuestId) // every difficulty; t.ChapterId has Normal only
		if chapter == 0 {
			chapter = t.ChapterId
		}
		collection = collectionPermil(collectionBonusCatalog(), user, chapter, masterdata.CollectionBonusDropRate, nowMillis)
	}
	type rate struct {
		grouping, permil, itemGroup int32
	}
	var rates []rate
	ie := h.ImportantItemEffects
	if ie != nil {
		for _, e := range ie.DropRates {
			if user.ImportantItems[e.ImportantItemId] <= 0 || nowMillis < e.StartDatetime || nowMillis > e.EndDatetime {
				continue
			}
			if !h.importantItemQuestMatches(e.QuestGroupId, t) {
				continue
			}
			rates = append(rates, rate{e.GroupingId, e.RatePermil, e.ItemGroupId})
		}
	}
	if len(rates) == 0 && collection == 0 {
		return nil
	}
	// A target group names a memoir by one rank variant; any variant of the
	// same memoir (group and rarity) matches, its rank being rolled at grant.
	kinds := listedDropCatalog().Parts
	matches := func(itemGroup int32, pt model.PossessionType, id int32) bool {
		if ie.ItemMatches(itemGroup, int32(pt), id) {
			return true
		}
		k, ok := kinds[id]
		if pt != model.PossessionTypeParts || !ok {
			return false
		}
		for _, r := range ie.ItemGroups[itemGroup] {
			if model.PossessionType(r.PossessionType) == model.PossessionTypeParts {
				if rk, ok := kinds[r.PossessionId]; ok && rk == k {
					return true
				}
			}
		}
		return false
	}
	return func(pt model.PossessionType, id int32) int64 {
		best := map[int32]int32{}
		for _, r := range rates {
			if matches(r.itemGroup, pt, id) && r.permil > best[r.grouping] {
				best[r.grouping] = r.permil
			}
		}
		sum := collection
		for _, p := range best {
			sum += int64(p)
		}
		return sum
	}
}
