package service

import (
	"strconv"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// The guerrilla quests' force unlock (Subquests › Guerrilla Quests › Unlock).
// The game offers it free DailyOpenMaxCount times a day
// (m_event_quest_guerrilla_free_open), then for NECESSARY_GEM_COUNT_FOR_GUERRILLA_OPEN
// gems (m_config, 100), free gems first; the uses reset at the daily reset.
// The client checks the player has the gems; the server takes them.

// guerrillaTerm finds the unlock row valid at now: its free uses a day and how long an
// unlock lasts. The Original calendar moves this table with the rest of the game data, so
// early in a loop (before 10 September 2021 in the live service) there is none and the
// game offers the unlock for "0m"; it must not open or take gems then.
func guerrillaTerm(rows []masterdata.EntityMEventQuestGuerrillaFreeOpen, now int64) (freePerDay, minutes int32, ok bool) {
	for _, row := range rows {
		if row.StartDatetime <= now && now < row.EndDatetime {
			return row.DailyOpenMaxCount, row.OpenMinutes, true
		}
	}
	return 0, 0, false
}

// guerrillaRules reads the unlock row valid at now and the gem price.
func guerrillaRules(now int64) (freePerDay, gemCost, minutes int32, ok bool) {
	if rows, err := utils.ReadTable[masterdata.EntityMEventQuestGuerrillaFreeOpen]("m_event_quest_guerrilla_free_open"); err == nil {
		freePerDay, minutes, ok = guerrillaTerm(rows, now)
	}
	if rows, err := utils.ReadTable[masterdata.EntityMConfig]("m_config"); err == nil {
		for _, row := range rows {
			if row.ConfigKey == "NECESSARY_GEM_COUNT_FOR_GUERRILLA_OPEN" {
				if v, err := strconv.ParseInt(row.Value, 10, 32); err == nil {
					gemCost = int32(v)
				}
			}
		}
	}
	return freePerDay, gemCost, minutes, ok
}

// openGuerrilla unlocks the guerrilla quests from now for minutes, charging gemCost gems once
// today's free uses (from dayStart) are spent. Without enough gems nothing changes.
func openGuerrilla(user *store.UserState, now, dayStart int64, freePerDay, gemCost, minutes int32) error {
	opened := user.GuerrillaFreeOpen.DailyOpenedCount
	if user.GuerrillaFreeOpen.StartDatetime < dayStart {
		opened = 0
	}
	if opened >= freePerDay && gemCost > 0 {
		if err := store.DeductPrice(user, model.PriceTypeGem, 0, gemCost); err != nil {
			return err
		}
	}
	user.GuerrillaFreeOpen.StartDatetime = now
	user.GuerrillaFreeOpen.OpenMinutes = minutes
	user.GuerrillaFreeOpen.DailyOpenedCount = opened + 1
	user.GuerrillaFreeOpen.LatestVersion = now
	return nil
}
