package service

// Start a new day (gametime.StartOfDay): the game shows a daily-limited
// quest's plays left, and Big Hunt's challenges left, from the count while the
// last one's time is today. After a press, a count from before it is
// yesterday's, but the game would still read its time as today; game start
// (which follows every press: the game is closed) zeroes it, as it refills
// shop stock.

import (
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/store"
)

func resetDailyCounts(user *store.UserState, nowMillis int64) {
	today := gametime.StartOfDay(nowMillis)
	for id, q := range user.Quests {
		if q.DailyClearCount != 0 && q.LastClearDatetime < today {
			q.DailyClearCount = 0
			user.Quests[id] = q
		}
	}
	for id, st := range user.BigHuntStatuses {
		if st.DailyChallengeCount != 0 && st.LatestChallengeDatetime < today {
			st.DailyChallengeCount = 0
			user.BigHuntStatuses[id] = st
		}
	}
}
