package store

import (
	"testing"
	"time"

	"lunar-tear/server/internal/model"
)

func TestUpgradeTimeKeys(t *testing.T) {
	ms := func(s string) int64 {
		v, err := time.Parse(time.RFC3339, s)
		if err != nil {
			t.Fatal(err)
		}
		return v.UnixMilli()
	}
	oldWeek, newWeek := ms("2024-07-01T00:00:00Z"), ms("2024-07-01T08:00:00Z")
	now := ms("2024-07-03T12:00:00Z")
	u := SeedUserState(1, "u", 0, model.DefaultPlatform)
	u.BigHuntWeeklyMaxScores[BigHuntWeeklyScoreKey{BigHuntWeeklyVersion: oldWeek, AttributeType: 2}] = BigHuntWeeklyMaxScore{MaxScore: 900, LatestVersion: 5}
	u.BigHuntWeeklyMaxScores[BigHuntWeeklyScoreKey{BigHuntWeeklyVersion: newWeek, AttributeType: 2}] = BigHuntWeeklyMaxScore{MaxScore: 400, LatestVersion: 7}
	u.BigHuntWeeklyMaxScores[BigHuntWeeklyScoreKey{BigHuntWeeklyVersion: oldWeek, AttributeType: 3}] = BigHuntWeeklyMaxScore{MaxScore: 300}
	u.BigHuntWeeklyStatuses[oldWeek] = BigHuntWeeklyStatus{IsReceivedWeeklyReward: true, LatestVersion: 5}
	u.BigHuntStatuses[11] = BigHuntStatus{LastDailyRewardReceivedDayVersion: ms("2024-07-03T00:00:00Z"), LatestVersion: 1}
	u.Ext.Pvp.WeekVersion, u.Ext.Pvp.RewardWeekVersion = oldWeek, oldWeek-7*24*3600*1000
	u.Ext.Pvp.Weekly = []PvpWeeklyResult{{WeekVersion: oldWeek - 7*24*3600*1000}}
	u.Ext.Friends.Day = ms("2024-07-03T00:00:00Z")

	UpgradeTimeKeys(u, now)
	UpgradeTimeKeys(u, now) // idempotent

	if len(u.BigHuntWeeklyMaxScores) != 2 ||
		u.BigHuntWeeklyMaxScores[BigHuntWeeklyScoreKey{BigHuntWeeklyVersion: newWeek, AttributeType: 2}] != (BigHuntWeeklyMaxScore{MaxScore: 900, LatestVersion: 7}) ||
		u.BigHuntWeeklyMaxScores[BigHuntWeeklyScoreKey{BigHuntWeeklyVersion: newWeek, AttributeType: 3}].MaxScore != 300 {
		t.Fatalf("weekly max scores %+v", u.BigHuntWeeklyMaxScores)
	}
	if len(u.BigHuntWeeklyStatuses) != 1 || !u.BigHuntWeeklyStatuses[newWeek].IsReceivedWeeklyReward {
		t.Fatalf("weekly statuses %+v", u.BigHuntWeeklyStatuses)
	}
	if got := u.BigHuntStatuses[11].LastDailyRewardReceivedDayVersion; got != ms("2024-07-03T08:00:00Z") {
		t.Fatalf("daily reward day %d", got)
	}
	p := u.Ext.Pvp
	if p.WeekVersion != newWeek || p.RewardWeekVersion != newWeek-7*24*3600*1000 || p.Weekly[0].WeekVersion != p.RewardWeekVersion {
		t.Fatalf("arena weeks %+v", p)
	}
	if u.Ext.Friends.Day != ms("2024-07-03T08:00:00Z") {
		t.Fatalf("cheer day %d", u.Ext.Friends.Day)
	}
}

// A daily claim made between UTC midnight and 08:00 UTC on the switch day
// counts for the current GMT-8 day, so it isn't due again the same day; it
// moves once only.
func TestUpgradeDailyTimestamps(t *testing.T) {
	start := time.Date(2026, 10, 13, 8, 0, 0, 0, time.UTC).UnixMilli() // 00:00 GMT-8
	now := start + 3*3600*1000
	claimed := start - 6*3600*1000 // 02:00 UTC
	old := start - 30*3600*1000    // the day before: left alone
	u := SeedUserState(1, "u", 0, model.DefaultPlatform)
	u.LoginBonus.LatestRewardReceiveDatetime = claimed
	u.Gacha.LastRewardDrawDate = old
	UpgradeTimeKeys(u, now)
	if u.LoginBonus.LatestRewardReceiveDatetime != start || u.Gacha.LastRewardDrawDate != old || u.Ext.TimeKeysVersion != 1 {
		t.Fatalf("login %d (want %d), draw %d, version %d", u.LoginBonus.LatestRewardReceiveDatetime, start, u.Gacha.LastRewardDrawDate, u.Ext.TimeKeysVersion)
	}
	u.LoginBonus.LatestRewardReceiveDatetime = claimed
	UpgradeTimeKeys(u, now)
	if u.LoginBonus.LatestRewardReceiveDatetime != claimed {
		t.Error("daily timestamps moved a second time")
	}
}
