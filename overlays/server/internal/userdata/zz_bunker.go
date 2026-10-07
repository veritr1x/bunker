package userdata

// Tables for Bunker's save additions (store.ExtState). The file name sorts
// last so these projections replace the empty placeholders registered earlier.

import (
	"log"
	"sort"
	"sync"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

func init() {
	register("IUserMissionPassPoint", func(user store.UserState) string {
		ids := sortedKeys(user.Ext.MissionPass)
		rows := make([]map[string]any, 0, len(ids))
		for _, id := range ids {
			p := user.Ext.MissionPass[id]
			rows = append(rows, map[string]any{
				"userId":                       user.UserId,
				"missionPassId":                p.MissionPassId,
				"point":                        p.Point,
				"premiumRewardReceivedLevel":   p.PremiumRewardReceivedLevel,
				"noPremiumRewardReceivedLevel": p.NoPremiumRewardReceivedLevel,
				"latestVersion":                p.LatestVersion,
			})
		}
		s, _ := utils.EncodeJSONMaps(rows...)
		return s
	})
	register("IUserEventQuestDailyGroupCompleteReward", func(user store.UserState) string {
		r := user.Ext.DailyGroupReward
		if r.LastRewardReceiveDatetime == 0 {
			return "[]"
		}
		s, _ := utils.EncodeJSONMaps(map[string]any{
			"userId": user.UserId,
			"lastRewardReceiveEventQuestDailyGroupId": r.LastRewardReceiveEventQuestDailyGroupId,
			"lastRewardReceiveDatetime":               r.LastRewardReceiveDatetime,
			"latestVersion":                           r.LatestVersion,
		})
		return s
	})
	register("IUserQuestSceneChoice", func(user store.UserState) string {
		ids := sortedKeys(user.Ext.SceneChoices)
		rows := make([]map[string]any, 0, len(ids))
		for _, id := range ids {
			c := user.Ext.SceneChoices[id]
			rows = append(rows, map[string]any{
				"userId":                     user.UserId,
				"questSceneChoiceGroupingId": c.QuestSceneChoiceGroupingId,
				"questSceneChoiceEffectId":   c.QuestSceneChoiceEffectId,
				"latestVersion":              c.LatestVersion,
			})
		}
		s, _ := utils.EncodeJSONMaps(rows...)
		return s
	})
	register("IUserQuestSceneChoiceHistory", func(user store.UserState) string {
		ids := sortedKeys(user.Ext.SceneChoiceHistory)
		rows := make([]map[string]any, 0, len(ids))
		for _, id := range ids {
			at := user.Ext.SceneChoiceHistory[id]
			rows = append(rows, map[string]any{
				"userId":                   user.UserId,
				"questSceneChoiceEffectId": id,
				"choiceDatetime":           at,
				"latestVersion":            at,
			})
		}
		s, _ := utils.EncodeJSONMaps(rows...)
		return s
	})
	register("IUserCostumeLevelBonusReleaseStatus", func(user store.UserState) string {
		s, _ := utils.EncodeJSONMaps(levelBonusRecords(user)...)
		return s
	})
	register("IUserPvpStatus", func(user store.UserState) string {
		p := user.Ext.Pvp
		milli, at := p.BattlePointMilli, p.BattlePointUpdated
		if at == 0 {
			milli = 100 * 1000 // never in the Arena: full (PVP_MAX_BATTLE_POINT)
		}
		s, _ := utils.EncodeJSONMaps(map[string]any{
			"userId":                              user.UserId,
			"staminaMilliValue":                   milli,
			"staminaUpdateDatetime":               at,
			"latestRewardReceivePvpSeasonId":      p.RewardSeasonId,
			"latestRewardReceivePvpWeeklyVersion": p.RewardWeekVersion,
			"winStreakCount":                      p.WinStreak,
			"winStreakCountUpdateDatetime":        p.WinStreakUpdated,
			"latestVersion":                       p.LatestVersion,
		})
		return s
	})
	register("IUserPvpDefenseDeck", func(user store.UserState) string {
		p := user.Ext.Pvp
		if p.DefenseDeckNumber == 0 {
			return "[]"
		}
		s, _ := utils.EncodeJSONMaps(map[string]any{
			"userId":         user.UserId,
			"userDeckNumber": p.DefenseDeckNumber,
			"latestVersion":  p.LatestVersion,
		})
		return s
	})
	register("IUserPvpWeeklyResult", func(user store.UserState) string {
		rows := make([]map[string]any, 0, len(user.Ext.Pvp.Weekly))
		for _, w := range user.Ext.Pvp.Weekly {
			rows = append(rows, map[string]any{
				"userId":           user.UserId,
				"pvpWeeklyVersion": w.WeekVersion,
				"pvpSeasonId":      w.SeasonId,
				"groupId":          w.GroupId,
				"finalPoint":       w.FinalPoint,
				"finalRank":        w.FinalRank,
				"latestVersion":    w.WeekVersion,
			})
		}
		s, _ := utils.EncodeJSONMaps(rows...)
		return s
	})
}

func sortedKeys[V any](m map[int32]V) []int32 {
	ids := make([]int32, 0, len(m))
	for id := range m {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	return ids
}

type levelBonusTables struct {
	bonusId map[int32]int32   // CostumeId -> CostumeLevelBonusId
	levels  map[int32][]int32 // CostumeLevelBonusId -> bonus levels, ascending
}

var levelBonuses = sync.OnceValue(func() levelBonusTables {
	t := levelBonusTables{bonusId: map[int32]int32{}, levels: map[int32][]int32{}}
	costumes, err := utils.ReadTable[masterdata.EntityMCostume]("m_costume")
	if err != nil {
		log.Printf("[userdata] m_costume: %v", err)
	}
	for _, c := range costumes {
		t.bonusId[c.CostumeId] = c.CostumeLevelBonusId
	}
	bonuses, err := utils.ReadTable[masterdata.EntityMCostumeLevelBonus]("m_costume_level_bonus")
	if err != nil {
		log.Printf("[userdata] m_costume_level_bonus: %v", err)
	}
	for _, b := range bonuses {
		t.levels[b.CostumeLevelBonusId] = append(t.levels[b.CostumeLevelBonusId], b.Level)
	}
	for _, l := range t.levels {
		sort.Slice(l, func(i, j int) bool { return l[i] < l[j] })
	}
	return t
})

// LevelBonusReleased is the highest level bonus a costume at this level has released (0: none).
func LevelBonusReleased(costumeId, level int32) int32 {
	t := levelBonuses()
	var released int32
	for _, l := range t.levels[t.bonusId[costumeId]] {
		if l <= level {
			released = l
		}
	}
	return released
}

// levelBonusRecords: for each owned costume with a released level bonus, the
// highest bonus released and the highest the player has seen. The game shows
// the bonus popup while the first is above the second. Bonuses at level 1 come
// with the costume and count as seen.
func levelBonusRecords(user store.UserState) []map[string]any {
	best, version := map[int32]int32{}, map[int32]int64{}
	for _, c := range user.Costumes {
		best[c.CostumeId] = max(best[c.CostumeId], c.Level)
		version[c.CostumeId] = max(version[c.CostumeId], c.LatestVersion, c.AcquisitionDatetime)
	}
	ids := sortedKeys(best)
	rows := make([]map[string]any, 0, len(ids))
	for _, id := range ids {
		released := LevelBonusReleased(id, best[id])
		if released == 0 {
			continue
		}
		confirmed, ok := user.Ext.LevelBonusConfirmed[id]
		if !ok {
			confirmed = LevelBonusReleased(id, 1)
		}
		rows = append(rows, map[string]any{
			"userId":                 user.UserId,
			"costumeId":              id,
			"lastReleasedBonusLevel": released,
			"confirmedBonusLevel":    confirmed,
			"latestVersion":          version[id],
		})
	}
	return rows
}

// bunkerChangedTables lists the client tables for ExtState that changed.
func bunkerChangedTables(before, after *store.UserState) []string {
	var out []string
	if !mapsEqualSimple(before.Ext.MissionPass, after.Ext.MissionPass) {
		out = append(out, "IUserMissionPassPoint")
	}
	if before.Ext.DailyGroupReward != after.Ext.DailyGroupReward {
		out = append(out, "IUserEventQuestDailyGroupCompleteReward")
	}
	if !mapsEqualSimple(before.Ext.SceneChoices, after.Ext.SceneChoices) {
		out = append(out, "IUserQuestSceneChoice")
	}
	if !mapsEqualSimple(before.Ext.SceneChoiceHistory, after.Ext.SceneChoiceHistory) {
		out = append(out, "IUserQuestSceneChoiceHistory")
	}
	if !mapsEqualSimple(before.Ext.LevelBonusConfirmed, after.Ext.LevelBonusConfirmed) || !costumeLevelsEqual(before, after) {
		out = append(out, "IUserCostumeLevelBonusReleaseStatus")
	}
	if b, a := before.Ext.Pvp, after.Ext.Pvp; b.BattlePointMilli != a.BattlePointMilli || b.BattlePointUpdated != a.BattlePointUpdated ||
		b.RewardSeasonId != a.RewardSeasonId || b.RewardWeekVersion != a.RewardWeekVersion ||
		b.WinStreak != a.WinStreak || b.WinStreakUpdated != a.WinStreakUpdated {
		out = append(out, "IUserPvpStatus")
	}
	if before.Ext.Pvp.DefenseDeckNumber != after.Ext.Pvp.DefenseDeckNumber {
		out = append(out, "IUserPvpDefenseDeck")
	}
	if len(before.Ext.Pvp.Weekly) != len(after.Ext.Pvp.Weekly) {
		out = append(out, "IUserPvpWeeklyResult")
	}
	return out
}

func costumeLevelsEqual(before, after *store.UserState) bool {
	if len(before.Costumes) != len(after.Costumes) {
		return false
	}
	for id, c := range after.Costumes {
		if b, ok := before.Costumes[id]; !ok || b.Level != c.Level {
			return false
		}
	}
	return true
}

func bunkerKeyFields(table string) []string {
	switch table {
	case "IUserMissionPassPoint":
		return []string{"userId", "missionPassId"}
	case "IUserEventQuestDailyGroupCompleteReward":
		return []string{"userId"}
	case "IUserQuestSceneChoice":
		return []string{"userId", "questSceneChoiceGroupingId"}
	case "IUserQuestSceneChoiceHistory":
		return []string{"userId", "questSceneChoiceEffectId"}
	case "IUserCostumeLevelBonusReleaseStatus":
		return []string{"userId", "costumeId"}
	case "IUserPvpStatus", "IUserPvpDefenseDeck":
		return []string{"userId"}
	case "IUserPvpWeeklyResult":
		return []string{"userId", "pvpWeeklyVersion"}
	}
	return nil
}
