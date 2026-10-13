package store

import "lunar-tear/server/internal/gametime"

// UpgradeTimeKeys moves day and week keys an older save stored at UTC
// midnight to the game's GMT-8 boundaries (see gametime). Timestamps need no
// change; only values that name a day or a week do. It is idempotent.
func UpgradeTimeKeys(u *UserState, now int64) {
	for id, st := range u.BigHuntStatuses {
		if v := gametime.UpgradeDayVersion(st.LastDailyRewardReceivedDayVersion, now); v != st.LastDailyRewardReceivedDayVersion {
			st.LastDailyRewardReceivedDayVersion = v
			u.BigHuntStatuses[id] = st
		}
	}
	for k, v := range u.BigHuntWeeklyMaxScores {
		if !gametime.IsLegacyWeekVersion(k.BigHuntWeeklyVersion) {
			continue
		}
		delete(u.BigHuntWeeklyMaxScores, k)
		k.BigHuntWeeklyVersion = gametime.UpgradeWeekVersion(k.BigHuntWeeklyVersion)
		if cur, ok := u.BigHuntWeeklyMaxScores[k]; ok {
			v.MaxScore = max(v.MaxScore, cur.MaxScore)
			v.LatestVersion = max(v.LatestVersion, cur.LatestVersion)
		}
		u.BigHuntWeeklyMaxScores[k] = v
	}
	for ver, v := range u.BigHuntWeeklyStatuses {
		if !gametime.IsLegacyWeekVersion(ver) {
			continue
		}
		delete(u.BigHuntWeeklyStatuses, ver)
		ver = gametime.UpgradeWeekVersion(ver)
		if cur, ok := u.BigHuntWeeklyStatuses[ver]; ok {
			v.IsReceivedWeeklyReward = v.IsReceivedWeeklyReward || cur.IsReceivedWeeklyReward
			v.LatestVersion = max(v.LatestVersion, cur.LatestVersion)
		}
		u.BigHuntWeeklyStatuses[ver] = v
	}

	p := &u.Ext.Pvp
	p.WeekVersion = gametime.UpgradeWeekVersion(p.WeekVersion)
	p.RewardWeekVersion = gametime.UpgradeWeekVersion(p.RewardWeekVersion)
	for i := range p.Weekly {
		p.Weekly[i].WeekVersion = gametime.UpgradeWeekVersion(p.Weekly[i].WeekVersion)
	}
	u.Ext.Friends.Day = gametime.UpgradeDayVersion(u.Ext.Friends.Day, now)
	upgradeDailyTimestamps(u, now)
}

// upgradeDailyTimestamps runs once per save. A daily reward or count recorded
// between UTC midnight and 08:00 UTC of the day the switch happens belonged to
// the old UTC day but falls in the previous GMT-8 day, so it would be due again
// a few hours later. Such timestamps move to the start of the current GMT-8
// day ("the latest day it could stand for", as UpgradeDayVersion does).
func upgradeDailyTimestamps(u *UserState, now int64) {
	if u.Ext.TimeKeysVersion >= 1 {
		return
	}
	u.Ext.TimeKeysVersion = 1
	start := gametime.StartOfDay(now)
	fix := func(t *int64) {
		if *t >= start-8*3600*1000 && *t < start {
			*t = start
		}
	}
	fix(&u.LoginBonus.LatestRewardReceiveDatetime)
	fix(&u.Login.LastLoginDatetime)
	fix(&u.Gacha.LastRewardDrawDate)
	fix(&u.Ext.DailyGroupReward.LastRewardReceiveDatetime)
	for id, st := range u.BigHuntStatuses {
		fix(&st.LatestChallengeDatetime)
		u.BigHuntStatuses[id] = st
	}
	for id, q := range u.Quests {
		fix(&q.LastClearDatetime)
		u.Quests[id] = q
	}
	for id, it := range u.ShopItems {
		fix(&it.LatestBoughtCountChangedDatetime)
		u.ShopItems[id] = it
	}
	for id, m := range u.Missions {
		fix(&m.StartDatetime)
		u.Missions[id] = m
	}
}
