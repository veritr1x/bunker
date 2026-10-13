package service

import (
	"log"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// The Original calendar (see gametime.Calendar) runs at game start: event
// items whose term has ended leave the inventory, and when a new loop has
// begun the rotating progress starts over, as the original reruns did.

// neverEnds is the date the calendar's game data gives content that stays
// once released (31 December 2099); anything ending earlier rotates.
const neverEnds = int64(4102444799000)

func calendarGameStart(u *store.UserState, now int64) {
	c := gametime.CurrentCalendar()
	if c == nil {
		return
	}
	switch loop := int32(c.Loop); {
	case u.Ext.CalendarLoop == 0:
		// Joining the calendar keeps everything earned so far.
		u.Ext.CalendarLoop = loop
	case u.Ext.CalendarLoop < loop:
		resetRotatingProgress(u)
		u.Ext.CalendarLoop = loop
		log.Printf("[Calendar] user %d: loop %d started, rotating progress reset", u.UserId, loop)
	}
	removeExpiredItems(u, now)
}

func table[T any](name string) []T {
	rows, err := utils.ReadTable[T](name)
	if err != nil {
		log.Printf("[Calendar] %s: %v", name, err)
	}
	return rows
}

// removeExpiredItems takes event items (medals, tickets) whose item term has
// ended. Summon medals are left to the summon page, which converts them.
func removeExpiredItems(u *store.UserState, now int64) {
	medals := map[int32]bool{}
	for _, m := range table[masterdata.EntityMGachaMedal]("m_gacha_medal") {
		medals[m.ConsumableItemId] = true
	}
	ended := map[int32]bool{}
	for _, t := range table[masterdata.EntityMConsumableItemTerm]("m_consumable_item_term") {
		if t.EndDatetime != 0 && t.EndDatetime <= now {
			ended[t.ConsumableItemTermId] = true
		}
	}
	for _, item := range table[masterdata.EntityMConsumableItem]("m_consumable_item") {
		if item.ConsumableItemTermId == 0 || !ended[item.ConsumableItemTermId] || medals[item.ConsumableItemId] {
			continue
		}
		if u.ConsumableItems[item.ConsumableItemId] > 0 {
			log.Printf("[Calendar] user %d: item %d expired (%d)", u.UserId, item.ConsumableItemId, u.ConsumableItems[item.ConsumableItemId])
			delete(u.ConsumableItems, item.ConsumableItemId)
		}
	}
}

// resetRotatingProgress clears what reruns in the next loop: event quests and
// their missions, event and limited missions, exchange shop purchases, the
// mission pass, login bonus calendars, Labyrinth seasons, Big Hunt records,
// limited summon progress and the pop-ups already seen. Characters, weapons,
// items, the main story and the play history are kept.
func resetRotatingProgress(u *store.UserState) {
	// Event quests of chapters that close again.
	sequences := map[int32][]int32{}
	for _, s := range table[masterdata.EntityMEventQuestSequence]("m_event_quest_sequence") {
		sequences[s.EventQuestSequenceId] = append(sequences[s.EventQuestSequenceId], s.QuestId)
	}
	groups := map[int32][]int32{}
	for _, g := range table[masterdata.EntityMEventQuestSequenceGroup]("m_event_quest_sequence_group") {
		groups[g.EventQuestSequenceGroupId] = append(groups[g.EventQuestSequenceGroupId], sequences[g.EventQuestSequenceId]...)
	}
	quests := map[int32]bool{}
	for _, ch := range table[masterdata.EntityMEventQuestChapter]("m_event_quest_chapter") {
		if ch.EndDatetime < neverEnds {
			for _, q := range groups[ch.EventQuestSequenceGroupId] {
				quests[q] = true
			}
			if u.EventQuest.CurrentEventQuestChapterId == ch.EventQuestChapterId {
				u.EventQuest = store.EventQuestState{}
			}
		}
	}
	for q := range u.Quests {
		if quests[q] {
			delete(u.Quests, q)
		}
	}
	for k := range u.QuestMissions {
		if quests[k.QuestId] {
			delete(u.QuestMissions, k)
		}
	}

	// Missions with a term that ends.
	terms := map[int32]bool{}
	for _, t := range table[masterdata.EntityMMissionTerm]("m_mission_term") {
		if t.EndDatetime < neverEnds {
			terms[t.MissionTermId] = true
		}
	}
	for _, m := range table[masterdata.EntityMMission]("m_mission") {
		if terms[m.MissionTermId] {
			delete(u.Missions, m.MissionId)
		}
	}

	// Purchases in shops that close.
	cells := map[int32]int32{}
	for _, c := range table[masterdata.EntityMShopItemCell]("m_shop_item_cell") {
		cells[c.ShopItemCellId] = c.ShopItemId
	}
	cellGroups := map[int32][]int32{}
	for _, g := range table[masterdata.EntityMShopItemCellGroup]("m_shop_item_cell_group") {
		cellGroups[g.ShopItemCellGroupId] = append(cellGroups[g.ShopItemCellGroupId], cells[g.ShopItemCellId])
	}
	for _, s := range table[masterdata.EntityMShop]("m_shop") {
		if s.EndDatetime < neverEnds {
			for _, item := range cellGroups[s.ShopItemCellGroupId] {
				delete(u.ShopItems, item)
			}
		}
	}

	// Step-up and pity progress of summons that end.
	for _, b := range table[masterdata.EntityMMomBanner]("m_mom_banner") {
		if b.DestinationDomainType == 1 && b.EndDatetime < neverEnds {
			delete(u.Gacha.BannerStates, b.DestinationDomainId)
		}
	}

	u.Ext.MissionPass = map[int32]store.MissionPassPointState{}
	u.PremiumItems = map[int32]int64{}
	u.LoginBonus = store.UserLoginBonusState{}
	u.LabyrinthSeasons = map[int32]store.LabyrinthSeasonState{}
	u.LabyrinthStages = map[store.LabyrinthStageKey]store.LabyrinthStageState{}
	u.BigHuntScheduleMaxScores = map[store.BigHuntScheduleScoreKey]store.BigHuntScheduleMaxScore{}
	u.BigHuntWeeklyMaxScores = map[store.BigHuntWeeklyScoreKey]store.BigHuntWeeklyMaxScore{}
	u.BigHuntWeeklyStatuses = map[int64]store.BigHuntWeeklyStatus{}
	u.DokanConfirmed = map[int32]bool{}
	u.Ext.DailyGroupReward = store.DailyGroupRewardState{}
}
