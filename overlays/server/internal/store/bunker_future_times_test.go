package store

import (
	"testing"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
)

// After the game clock goes back (the calendar turned off after a jump or a
// faster speed), times saved on a later game day would read as "done today"
// until the real date caught up. They move to the end of the previous day.
func TestFutureDailyTimesMoveBeforeToday(t *testing.T) {
	const day = 24 * 3600 * 1000
	now := gametime.BaseStartOfDay(1_780_000_000_000) + 12*3600*1000
	today := gametime.StartOfDay(now)
	future, laterToday, past := now+20*day, now+3600*1000, now-3*day
	u := SeedUserState(1, "u", past, model.DefaultPlatform)
	u.Ext.TimeKeysVersion = 1 // past the one-off UTC-day upgrade

	u.Login.LastLoginDatetime = future
	u.LoginBonus.LatestRewardReceiveDatetime = future
	u.Gacha.LastRewardDrawDate = future
	u.Ext.DailyGroupReward.LastRewardReceiveDatetime = future
	u.Ext.EventLoginBonuses = map[int32]UserLoginBonusState{7: {LoginBonusId: 7, LatestRewardReceiveDatetime: future}}
	u.GuerrillaFreeOpen.StartDatetime = future
	u.ShopReplaceable.LatestLineupUpdateDatetime = future
	u.BigHuntStatuses[1] = BigHuntStatus{LatestChallengeDatetime: future, LastDailyRewardReceivedDayVersion: gametime.BaseStartOfDay(future)}
	u.Quests[1] = UserQuestState{QuestId: 1, LastClearDatetime: future, DailyClearCount: 3}
	u.Quests[2] = UserQuestState{QuestId: 2, LastClearDatetime: laterToday, DailyClearCount: 1}
	u.ShopItems[1] = UserShopItemState{ShopItemId: 1, LatestBoughtCountChangedDatetime: future, BoughtCount: 1}
	u.Missions[1] = UserMissionState{MissionId: 1, StartDatetime: future}
	u.Missions[2] = UserMissionState{MissionId: 2, StartDatetime: past}
	u.Ext.Pvp.WeekVersion = gametime.WeeklyVersion(future)

	UpgradeTimeKeys(u, now)

	before := func(name string, v int64) {
		t.Helper()
		if v >= today || v < today-day {
			t.Errorf("%s = %d, want during the previous day (today starts %d)", name, v, today)
		}
	}
	before("LastLoginDatetime", u.Login.LastLoginDatetime)
	before("login bonus", u.LoginBonus.LatestRewardReceiveDatetime)
	before("roulette", u.Gacha.LastRewardDrawDate)
	before("daily group reward", u.Ext.DailyGroupReward.LastRewardReceiveDatetime)
	before("event login bonus", u.Ext.EventLoginBonuses[7].LatestRewardReceiveDatetime)
	before("guerrilla", u.GuerrillaFreeOpen.StartDatetime)
	before("shop lineup", u.ShopReplaceable.LatestLineupUpdateDatetime)
	before("big hunt challenge", u.BigHuntStatuses[1].LatestChallengeDatetime)
	before("big hunt daily reward", u.BigHuntStatuses[1].LastDailyRewardReceivedDayVersion)
	before("quest clear", u.Quests[1].LastClearDatetime)
	before("shop stock", u.ShopItems[1].LatestBoughtCountChangedDatetime)
	before("mission start", u.Missions[1].StartDatetime)
	if w := gametime.WeeklyVersion(now); u.Ext.Pvp.WeekVersion != w {
		t.Errorf("Arena week %d, want this week %d", u.Ext.Pvp.WeekVersion, w)
	}
	// Times on the current day or earlier stay.
	if u.Quests[2].LastClearDatetime != laterToday || u.Missions[2].StartDatetime != past || u.Quests[1].DailyClearCount != 3 {
		t.Errorf("changed times that were not on a later day: %+v %+v", u.Quests[2], u.Missions[2])
	}
}
