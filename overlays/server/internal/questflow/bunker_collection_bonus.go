package questflow

import (
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// Costume collection bonuses (masterdata/bunker_collection_bonus.go) on a
// main-story clear: costume EXP, gold and drop rate.

var collectionBonusCatalog = masterdata.CollectionBonuses

// collectionPermil is the raise, in permil, of effect effectType that the
// player's costume sets give on main-quest chapter chapterId now (0 for
// anything else). A bonus applies once every costume of its set is owned,
// at the level of the lowest limit break across the set (each costume's best
// copy). Bonuses of one grouping don't stack: the largest counts.
func collectionPermil(bs []masterdata.CollectionBonus, user *store.UserState, chapterId, effectType int32, nowMillis int64) int64 {
	if chapterId == 0 {
		return 0
	}
	var best map[int32]int32 // grouping -> amount in percent
	var owned map[int32]int32
	for _, b := range bs {
		if b.EffectType != effectType || !b.MainChapters[chapterId] || nowMillis < b.StartDatetime || nowMillis > b.EndDatetime {
			continue
		}
		if owned == nil {
			owned = map[int32]int32{}
			for _, c := range user.Costumes {
				if lb, ok := owned[c.CostumeId]; !ok || c.LimitBreakCount > lb {
					owned[c.CostumeId] = c.LimitBreakCount
				}
			}
		}
		level := int32(len(b.Amounts) - 1)
		complete := true
		for _, id := range b.Costumes {
			lb, ok := owned[id]
			if !ok {
				complete = false
				break
			}
			level = min(level, max(lb, 0))
		}
		if !complete {
			continue
		}
		if best == nil {
			best = map[int32]int32{}
		}
		if a := b.Amounts[level]; a > best[b.GroupingId] {
			best[b.GroupingId] = a
		}
	}
	var permil int64
	for _, a := range best {
		permil += int64(a) * 10
	}
	return permil
}

// mainChapterCollectionPermil is collectionPermil for quest questId, a main
// quest when it has a chapter.
func (h *QuestHandler) mainChapterCollectionPermil(user *store.UserState, questId, effectType int32, nowMillis int64) int64 {
	return collectionPermil(collectionBonusCatalog(), user, h.MainQuestChapterIdByQuestId[questId], effectType, nowMillis)
}
