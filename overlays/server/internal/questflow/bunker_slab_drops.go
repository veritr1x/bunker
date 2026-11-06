package questflow

import (
	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/model"
)

// Slab Fragments from quests. In the live game they were random enemy drops
// rolled by the server (each battle's BattleDropBoxGroupId), and those tables
// never shipped in the master data: no story quest lists them among its drops,
// the guerrilla quests list only the Medium one and the dungeons none. The
// notices say story quests dropped Small and Medium ones (the monthly support
// campaigns guaranteed "at least one" of each), and the item's Location list
// names the guerrilla quests and the dungeons for the Small one. The amounts
// are an estimate.
const (
	smallSlabFragment  = 401001
	mediumSlabFragment = 401002

	eventQuestTypeDungeon   = 3 // The Dynast's Memories and the other memories dungeons
	eventQuestTypeGuerrilla = 5
)

// slabDrops is what a clear of a quest adds: on a story quest Small x1-3 and,
// one time in two, Medium x1; on a guerrilla quest or a dungeon Small x1.
// rate applies the quest's drop-rate campaign; roll(n) is in [0, n).
func slabDrops(t campaign.QuestTarget, rate func(int32) int32, roll func(int64) int64) []RewardGrant {
	slab := func(id, count int32) RewardGrant {
		return RewardGrant{PossessionType: model.PossessionTypeMaterial, PossessionId: id, Count: rate(count)}
	}
	switch {
	case t.QuestType == campaign.QuestTypeMainQuest:
		drops := []RewardGrant{slab(smallSlabFragment, 1+int32(roll(3)))}
		if roll(2) == 0 {
			drops = append(drops, slab(mediumSlabFragment, 1))
		}
		return drops
	case t.QuestType == campaign.QuestTypeEventQuest &&
		(t.EventQuestType == eventQuestTypeGuerrilla || t.EventQuestType == eventQuestTypeDungeon):
		return []RewardGrant{slab(smallSlabFragment, 1)}
	}
	return nil
}
