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

// guerrillaRules reads the free uses a day, the gem price and how long an unlock lasts.
func guerrillaRules() (freePerDay, gemCost, minutes int32) {
	freePerDay, minutes = 1, defaultGuerrillaFreeOpenMinutes
	if rows, err := utils.ReadTable[masterdata.EntityMEventQuestGuerrillaFreeOpen]("m_event_quest_guerrilla_free_open"); err == nil && len(rows) > 0 {
		freePerDay, minutes = rows[0].DailyOpenMaxCount, rows[0].OpenMinutes
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
	return freePerDay, gemCost, minutes
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
