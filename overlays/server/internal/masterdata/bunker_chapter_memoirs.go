package masterdata

import (
	"log"
	"slices"

	"lunar-tear/server/internal/bunkercache"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/utils"
)

// Event chapter memoirs. 25 event chapters show three memoirs on their
// chapter screen (m_event_quest_display_item_group), one from each of three
// series at rarity 40, 30 and 20, but their quests drop only the first
// series, at rarity 10 or 20. The rest were random enemy drops in the live
// game, from tables that never shipped (like Slab Fragments,
// questflow/bunker_slab_drops.go), so they could not be had at all. From the
// JCalandre/lunar-tear fork, which found the gap.

// ChapterMemoirs maps each quest of such a chapter to the memoirs its chapter
// shows that none of the chapter's quests drop (same series and rarity).
var ChapterMemoirs = bunkercache.Value(func() map[int32][]int32 {
	var t chapterMemoirTables
	read := func(err error, name string) {
		if err != nil {
			log.Printf("[ChapterMemoirs] %s: %v", name, err)
		}
	}
	var err error
	t.chapters, err = utils.ReadTable[EntityMEventQuestChapter]("m_event_quest_chapter")
	read(err, "m_event_quest_chapter")
	t.display, err = utils.ReadTable[EntityMEventQuestDisplayItemGroup]("m_event_quest_display_item_group")
	read(err, "m_event_quest_display_item_group")
	t.groups, err = utils.ReadTable[EntityMEventQuestSequenceGroup]("m_event_quest_sequence_group")
	read(err, "m_event_quest_sequence_group")
	t.sequences, err = utils.ReadTable[EntityMEventQuestSequence]("m_event_quest_sequence")
	read(err, "m_event_quest_sequence")
	t.quests, err = utils.ReadTable[EntityMQuest]("m_quest")
	read(err, "m_quest")
	t.pickups, err = utils.ReadTable[EntityMQuestPickupRewardGroup]("m_quest_pickup_reward_group")
	read(err, "m_quest_pickup_reward_group")
	t.battleDrops, err = utils.ReadTable[EntityMBattleDropReward]("m_battle_drop_reward")
	read(err, "m_battle_drop_reward")
	t.partsEntries, err = utils.ReadTable[EntityMParts]("m_parts")
	read(err, "m_parts")
	return chapterMemoirs(t)
})

type chapterMemoirTables struct {
	chapters     []EntityMEventQuestChapter
	display      []EntityMEventQuestDisplayItemGroup
	groups       []EntityMEventQuestSequenceGroup
	sequences    []EntityMEventQuestSequence
	quests       []EntityMQuest
	pickups      []EntityMQuestPickupRewardGroup
	battleDrops  []EntityMBattleDropReward
	partsEntries []EntityMParts
}

func chapterMemoirs(t chapterMemoirTables) map[int32][]int32 {
	type kind struct{ group, rarity int32 } // a memoir's five ranks share it
	partsKind := map[int32]kind{}
	for _, p := range t.partsEntries {
		partsKind[p.PartsId] = kind{p.PartsGroupId, p.RarityType}
	}
	shown := map[int32][]int32{}
	for _, d := range t.display {
		if model.PossessionType(d.PossessionType) == model.PossessionTypeParts {
			shown[d.EventQuestDisplayItemGroupId] = append(shown[d.EventQuestDisplayItemGroupId], d.PossessionId)
		}
	}
	drops := map[int32]EntityMBattleDropReward{}
	for _, d := range t.battleDrops {
		drops[d.BattleDropRewardId] = d
	}
	pickups := map[int32][]int32{}
	for _, p := range t.pickups {
		pickups[p.QuestPickupRewardGroupId] = append(pickups[p.QuestPickupRewardGroupId], p.BattleDropRewardId)
	}
	questPickup := map[int32]int32{}
	for _, q := range t.quests {
		questPickup[q.QuestId] = q.QuestPickupRewardGroupId
	}
	sequenceQuests := map[int32][]int32{}
	for _, s := range t.sequences {
		sequenceQuests[s.EventQuestSequenceId] = append(sequenceQuests[s.EventQuestSequenceId], s.QuestId)
	}
	groupSequences := map[int32][]int32{}
	for _, g := range t.groups {
		groupSequences[g.EventQuestSequenceGroupId] = append(groupSequences[g.EventQuestSequenceGroupId], g.EventQuestSequenceId)
	}

	out := map[int32][]int32{}
	for _, c := range t.chapters {
		memoirs := shown[c.EventQuestDisplayItemGroupId]
		if len(memoirs) == 0 {
			continue
		}
		var quests []int32
		dropped := map[kind]bool{}
		for _, seq := range groupSequences[c.EventQuestSequenceGroupId] {
			for _, q := range sequenceQuests[seq] {
				quests = append(quests, q)
				for _, id := range pickups[questPickup[q]] {
					if d := drops[id]; model.PossessionType(d.PossessionType) == model.PossessionTypeParts {
						dropped[partsKind[d.PossessionId]] = true
					}
				}
			}
		}
		var missing []int32
		for _, id := range memoirs {
			if k, ok := partsKind[id]; ok && !dropped[k] && !slices.Contains(missing, id) {
				missing = append(missing, id)
			}
		}
		if len(missing) == 0 {
			continue
		}
		slices.Sort(missing)
		for _, q := range quests {
			out[q] = missing
		}
	}
	return out
}
