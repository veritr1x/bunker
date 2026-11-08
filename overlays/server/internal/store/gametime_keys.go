package store

import (
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
)

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
	pullBackFutureDays(u, now)
	UpgradeChapterGachaIds(u)
}

// pullBackFutureDays moves times of once-a-day things saved on a later game
// day to the end of the previous day. The game clock goes back when the
// calendar is turned off after a jump or a faster speed; a time from the
// jumped-to day would otherwise read as "done today" until the real date
// caught up, keeping logins, daily missions, stamps, shop stock, Subjugation
// dailies and the roulette from starting over. The Arena week goes back to the
// current week the same way. Times on the current day are left alone, and so
// is the login streak: the previous day counts as a login.
func pullBackFutureDays(u *UserState, now int64) {
	const dayMillis = 24 * 3600 * 1000
	nextDay := gametime.BaseStartOfDay(now) + dayMillis
	yesterday := gametime.StartOfDay(now) - 1
	fix := func(t *int64) {
		if *t >= nextDay {
			*t = yesterday
		}
	}
	fix(&u.Login.LastLoginDatetime)
	fix(&u.LoginBonus.LatestRewardReceiveDatetime)
	fix(&u.Gacha.LastRewardDrawDate)
	fix(&u.GuerrillaFreeOpen.StartDatetime)
	fix(&u.ShopReplaceable.LatestLineupUpdateDatetime)
	fix(&u.Ext.DailyGroupReward.LastRewardReceiveDatetime)
	for id, st := range u.Ext.EventLoginBonuses {
		if st.LatestRewardReceiveDatetime >= nextDay {
			fix(&st.LatestRewardReceiveDatetime)
			u.Ext.EventLoginBonuses[id] = st
		}
	}
	for id, st := range u.BigHuntStatuses {
		if st.LatestChallengeDatetime >= nextDay || st.LastDailyRewardReceivedDayVersion >= nextDay {
			fix(&st.LatestChallengeDatetime)
			if st.LastDailyRewardReceivedDayVersion >= nextDay {
				st.LastDailyRewardReceivedDayVersion = gametime.BaseStartOfDay(yesterday)
			}
			u.BigHuntStatuses[id] = st
		}
	}
	for id, q := range u.Quests {
		if q.LastClearDatetime >= nextDay {
			fix(&q.LastClearDatetime)
			u.Quests[id] = q
		}
	}
	for id, it := range u.ShopItems {
		if it.LatestBoughtCountChangedDatetime >= nextDay {
			fix(&it.LatestBoughtCountChangedDatetime)
			u.ShopItems[id] = it
		}
	}
	for id, m := range u.Missions {
		if m.StartDatetime >= nextDay {
			fix(&m.StartDatetime)
			u.Missions[id] = m
		}
	}
	if week := gametime.WeeklyVersion(now); u.Ext.Pvp.WeekVersion > week {
		u.Ext.Pvp.WeekVersion = week
	}
}

// UpgradeChapterGachaIds moves chapter summon progress (box draws) from the
// old ids, 200000 + chapter, which "Mama's Dream" summons also use, to
// model.ChapterGachaIdBase + chapter. It runs once per save.
func UpgradeChapterGachaIds(u *UserState) {
	if u.Ext.ChapterGachaIds >= 1 {
		return
	}
	u.Ext.ChapterGachaIds = 1
	for id, st := range u.Gacha.BannerStates {
		chapter := id - model.LegacyChapterGachaIdBase
		if chapter < 0 || chapter > 99 {
			continue
		}
		delete(u.Gacha.BannerStates, id)
		st.GachaId = model.ChapterGachaIdBase + chapter
		u.Gacha.BannerStates[st.GachaId] = st
	}
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
