package masterdata

import (
	"fmt"
	"log"
	"sort"
	"sync"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// Chapter summons are paid with chapter tickets: permanent type-200
// consumables that drop in exactly one main quest chapter. One more ticket
// drops only in END_CONTENTS event chapters and pays for the "ex" summon.
// The tickets are found from the quest drop tables (quest pickup reward
// groups), so nothing here names a ticket or chapter by id.

const (
	consumableItemTypeTicket  int32 = 200
	eventQuestTypeEndContents int32 = 7
	questDifficultyTypeNormal int32 = 1
	chapterGachaSortOrderBase int32 = 9000
	chapterGachaAssetPrefix         = "chapter_"
	chapterGachaExAssetName         = "chapter_ex"
)

// ChapterTicket is one chapter summon: the ticket that pays for it and the
// main quest chapter whose quests drop the ticket (0 for the ex summon).
type ChapterTicket struct {
	Box                []store.GachaBoxContent // the chapter's materials (chapterBox)
	ConsumableItemId   int32
	MainQuestChapterId int32
	UnlockQuestId      int32 // last normal-difficulty quest of the chapter
	AssetName          string
}

// LoadChapterTickets derives the chapter summons from the drop tables.
// Main chapter tickets come first, ordered by ticket id; their banner assets
// are chapter_1..chapter_N in that order. The ex ticket, if any, is last.
func LoadChapterTickets() ([]ChapterTicket, error) {
	items, err := utils.ReadTable[EntityMConsumableItem]("m_consumable_item")
	if err != nil {
		return nil, fmt.Errorf("load consumable items: %w", err)
	}
	quests, err := utils.ReadTable[EntityMQuest]("m_quest")
	if err != nil {
		return nil, fmt.Errorf("load quests: %w", err)
	}
	pickups, err := utils.ReadTable[EntityMQuestPickupRewardGroup]("m_quest_pickup_reward_group")
	if err != nil {
		return nil, fmt.Errorf("load quest pickup reward groups: %w", err)
	}
	drops, err := utils.ReadTable[EntityMBattleDropReward]("m_battle_drop_reward")
	if err != nil {
		return nil, fmt.Errorf("load battle drop rewards: %w", err)
	}
	mainChapters, err := utils.ReadTable[EntityMMainQuestChapter]("m_main_quest_chapter")
	if err != nil {
		return nil, fmt.Errorf("load main quest chapters: %w", err)
	}
	mainGroups, err := utils.ReadTable[EntityMMainQuestSequenceGroup]("m_main_quest_sequence_group")
	if err != nil {
		return nil, fmt.Errorf("load main quest sequence groups: %w", err)
	}
	mainSequences, err := utils.ReadTable[EntityMMainQuestSequence]("m_main_quest_sequence")
	if err != nil {
		return nil, fmt.Errorf("load main quest sequences: %w", err)
	}
	eventChapters, err := utils.ReadTable[EntityMEventQuestChapter]("m_event_quest_chapter")
	if err != nil {
		return nil, fmt.Errorf("load event quest chapters: %w", err)
	}
	eventGroups, err := utils.ReadTable[EntityMEventQuestSequenceGroup]("m_event_quest_sequence_group")
	if err != nil {
		return nil, fmt.Errorf("load event quest sequence groups: %w", err)
	}
	eventSequences, err := utils.ReadTable[EntityMEventQuestSequence]("m_event_quest_sequence")
	if err != nil {
		return nil, fmt.Errorf("load event quest sequences: %w", err)
	}

	tickets := make(map[int32]bool)
	for _, it := range items {
		if it.ConsumableItemType == consumableItemTypeTicket && it.ConsumableItemTermId == 0 {
			tickets[it.ConsumableItemId] = true
		}
	}
	dropById := make(map[int32]EntityMBattleDropReward, len(drops))
	for _, d := range drops {
		dropById[d.BattleDropRewardId] = d
	}
	pickupDrops := make(map[int32][]int32)
	for _, p := range pickups {
		pickupDrops[p.QuestPickupRewardGroupId] = append(pickupDrops[p.QuestPickupRewardGroupId], p.BattleDropRewardId)
	}
	pickupByQuest := make(map[int32]int32, len(quests))
	for _, q := range quests {
		pickupByQuest[q.QuestId] = q.QuestPickupRewardGroupId
	}
	ticketsOfQuest := func(questId int32) []int32 {
		var out []int32
		for _, id := range pickupDrops[pickupByQuest[questId]] {
			d := dropById[id]
			if model.PossessionType(d.PossessionType) == model.PossessionTypeConsumableItem && tickets[d.PossessionId] {
				out = append(out, d.PossessionId)
			}
		}
		return out
	}

	mainQuestsBySequence := make(map[int32][]EntityMMainQuestSequence)
	for _, s := range mainSequences {
		mainQuestsBySequence[s.MainQuestSequenceId] = append(mainQuestsBySequence[s.MainQuestSequenceId], s)
	}
	mainGroupRows := make(map[int32][]EntityMMainQuestSequenceGroup)
	for _, g := range mainGroups {
		mainGroupRows[g.MainQuestSequenceGroupId] = append(mainGroupRows[g.MainQuestSequenceGroupId], g)
	}
	mainChaptersByTicket := make(map[int32]map[int32]bool)
	unlockQuestByChapter := make(map[int32]int32)
	questsByChapter := make(map[int32][]int32)
	questsByTicket := make(map[int32][]int32) // event quests dropping a ticket, for the ex summon
	for _, ch := range mainChapters {
		lastSort := int32(-1)
		for _, g := range mainGroupRows[ch.MainQuestSequenceGroupId] {
			for _, s := range mainQuestsBySequence[g.MainQuestSequenceId] {
				questsByChapter[ch.MainQuestChapterId] = append(questsByChapter[ch.MainQuestChapterId], s.QuestId)
				for _, t := range ticketsOfQuest(s.QuestId) {
					if mainChaptersByTicket[t] == nil {
						mainChaptersByTicket[t] = make(map[int32]bool)
					}
					mainChaptersByTicket[t][ch.MainQuestChapterId] = true
				}
				if g.DifficultyType == questDifficultyTypeNormal && s.SortOrder > lastSort {
					lastSort = s.SortOrder
					unlockQuestByChapter[ch.MainQuestChapterId] = s.QuestId
				}
			}
		}
	}

	eventQuestsBySequence := make(map[int32][]int32)
	for _, s := range eventSequences {
		eventQuestsBySequence[s.EventQuestSequenceId] = append(eventQuestsBySequence[s.EventQuestSequenceId], s.QuestId)
	}
	eventGroupSequences := make(map[int32][]int32)
	for _, g := range eventGroups {
		eventGroupSequences[g.EventQuestSequenceGroupId] = append(eventGroupSequences[g.EventQuestSequenceGroupId], g.EventQuestSequenceId)
	}
	// ticket -> whether every event chapter dropping it is END_CONTENTS
	eventOnlyEndContents := make(map[int32]bool)
	for _, ch := range eventChapters {
		for _, seqId := range eventGroupSequences[ch.EventQuestSequenceGroupId] {
			for _, questId := range eventQuestsBySequence[seqId] {
				for _, t := range ticketsOfQuest(questId) {
					questsByTicket[t] = append(questsByTicket[t], questId)
					prev, seen := eventOnlyEndContents[t]
					eventOnlyEndContents[t] = (!seen || prev) && ch.EventQuestType == eventQuestTypeEndContents
				}
			}
		}
	}

	var out []ChapterTicket
	for t, chapters := range mainChaptersByTicket {
		if len(chapters) != 1 {
			continue
		}
		if _, inEvents := eventOnlyEndContents[t]; inEvents {
			continue
		}
		for chapterId := range chapters {
			out = append(out, ChapterTicket{ConsumableItemId: t, MainQuestChapterId: chapterId, UnlockQuestId: unlockQuestByChapter[chapterId],
				Box: chapterBox(questsByChapter[chapterId], pickupDrops, pickupByQuest, dropById)})
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ConsumableItemId < out[j].ConsumableItemId })
	for i := range out {
		out[i].AssetName = fmt.Sprintf("%s%d", chapterGachaAssetPrefix, i+1)
	}

	var exTickets []int32
	for t, onlyEnd := range eventOnlyEndContents {
		if onlyEnd && mainChaptersByTicket[t] == nil {
			exTickets = append(exTickets, t)
		}
	}
	if len(exTickets) == 1 {
		out = append(out, ChapterTicket{ConsumableItemId: exTickets[0], AssetName: chapterGachaExAssetName,
			Box: chapterBox(questsByTicket[exTickets[0]], pickupDrops, pickupByQuest, dropById)})
	}
	return out, nil
}

// chapterGachaEntry is the box-mode summon paid with one chapter ticket. The
// pool is not in the client data; draws keep Bunker's material pool.
func chapterGachaEntry(t ChapterTicket) store.GachaCatalogEntry {
	gachaId := chapterGachaIdBase + t.MainQuestChapterId // the ex summon gets the base id
	e := store.GachaCatalogEntry{
		GachaId:                   gachaId,
		GachaLabelType:            model.GachaLabelChapter,
		GachaModeType:             model.GachaModeBox,
		GachaAutoResetType:        model.GachaAutoResetNone,
		IsUserGachaUnlock:         true,
		RelatedMainQuestChapterId: t.MainQuestChapterId,
		GachaDecorationType:       model.GachaDecorationNormal,
		BoxContents:               t.Box,
		SortOrder:                 chapterGachaSortOrderBase + t.MainQuestChapterId,
		BannerAssetName:           t.AssetName,
		GroupId:                   gachaId,
		PricePhases:               buildChapterPricePhases(gachaId, t.ConsumableItemId),
		UnlockConditionType:       model.GachaUnlockNone,
	}
	if t.UnlockQuestId != 0 {
		e.UnlockConditionType = model.GachaUnlockMainQuestClear
		e.UnlockConditionValue = t.UnlockQuestId
	}
	return e
}

// Box contents. Chapter summons gave the materials found in that chapter, from
// a box that refilled every month; the box itself is not in the game data. A
// chapter's box holds each material its quests drop, fewer of the rarer ones
// (chapterBoxCounts by rarity); the rarest are its targets.
var chapterBoxCounts = map[int32]int32{model.RarityNormal: 10, model.RarityRare: 6, model.RaritySRare: 3, model.RaritySSRare: 1}

var materialRarity = sync.OnceValue(func() map[int32]int32 {
	rows, err := utils.ReadTable[EntityMMaterial]("m_material")
	if err != nil {
		log.Printf("[ChapterGacha] m_material: %v", err)
	}
	out := make(map[int32]int32, len(rows))
	for _, m := range rows {
		out[m.MaterialId] = m.RarityType
	}
	return out
})

func chapterBox(quests []int32, pickupDrops map[int32][]int32, pickupByQuest map[int32]int32, dropById map[int32]EntityMBattleDropReward) []store.GachaBoxContent {
	seen := map[int32]bool{}
	var box []store.GachaBoxContent
	top := int32(0)
	for _, q := range quests {
		for _, id := range pickupDrops[pickupByQuest[q]] {
			d := dropById[id]
			if model.PossessionType(d.PossessionType) != model.PossessionTypeMaterial || seen[d.PossessionId] {
				continue
			}
			rarity, ok := materialRarity()[d.PossessionId]
			count := chapterBoxCounts[rarity]
			if !ok || count == 0 {
				continue
			}
			seen[d.PossessionId] = true
			box = append(box, store.GachaBoxContent{PossessionType: d.PossessionType, PossessionId: d.PossessionId, RarityType: rarity, Count: count})
			top = max(top, rarity)
		}
	}
	for i := range box {
		box[i].IsTarget = box[i].RarityType == top
	}
	sort.Slice(box, func(i, j int) bool {
		if box[i].RarityType != box[j].RarityType {
			return box[i].RarityType > box[j].RarityType
		}
		return box[i].PossessionId < box[j].PossessionId
	})
	return box
}
