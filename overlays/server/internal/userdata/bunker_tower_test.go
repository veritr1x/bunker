package userdata

import (
	"strings"
	"testing"

	"lunar-tear/server/internal/store"
)

// An Abyss Tower's runs are copies of its chapter (Original calendar); the
// rewards claimed are one record, shown under every run.
func TestTowerRewardsShowUnderEveryRun(t *testing.T) {
	user := store.UserState{UserId: 1}
	user.EnsureMaps()
	user.TowerAccumulationRewards[701] = store.TowerAccumulationRewardState{EventQuestChapterId: 701, LatestRewardReceiveQuestMissionClearCount: 10}
	got := projectTable("IUserEventQuestTowerAccumulationReward", user)
	for _, id := range []string{`"eventQuestChapterId":701,`, `"eventQuestChapterId":10000701,`, `"eventQuestChapterId":50000701,`} {
		if !strings.Contains(got, id) {
			t.Fatalf("no record for %s in %s", id, got)
		}
	}
}
