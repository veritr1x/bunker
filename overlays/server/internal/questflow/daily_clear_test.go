package questflow

import (
	"testing"
	"time"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

func TestDailyClearsStartOverOnGameDay(t *testing.T) {
	ms := func(s string) int64 {
		v, err := time.Parse(time.RFC3339, s)
		if err != nil {
			t.Fatal(err)
		}
		return v.UnixMilli()
	}
	q := store.UserQuestState{}
	addDailyClears(&q, 1, ms("2024-07-01T09:00:00Z"))
	addDailyClears(&q, 2, ms("2024-07-02T07:59:59Z")) // still July 1 in GMT-8
	if q.DailyClearCount != 3 {
		t.Fatalf("same game day: %d clears, want 3", q.DailyClearCount)
	}
	addDailyClears(&q, 1, ms("2024-07-02T08:00:00Z")) // a new game day
	if q.DailyClearCount != 1 || q.LastClearDatetime != ms("2024-07-02T08:00:00Z") {
		t.Fatalf("new game day: %+v", q)
	}
	addDailyClears(&q, 5, ms("2024-07-05T10:00:00Z"))
	if q.DailyClearCount != 5 {
		t.Fatalf("skip on a later day: %d clears, want 5", q.DailyClearCount)
	}
}

func TestLevelUpRefillsStaminaOnlyBelowMax(t *testing.T) {
	h := testHandler()
	h.QuestById[testQuest] = masterdata.EntityMQuest{QuestId: testQuest, UserExp: 100}
	h.UserExpThresholds = []int32{0, 0, 100, 1000}
	h.MaxStaminaByLevel = map[int32]int32{1: 50, 2: 51, 3: 52}

	for _, c := range []struct{ before, want int32 }{
		{10_000, 51_000},   // below the new max: filled to it
		{120_000, 120_000}, // above it: kept
	} {
		u := testUser()
		u.Status.Level, u.Status.Exp = 1, 0
		u.Status.StaminaMilliValue = c.before
		h.applyExpRewards(u, testQuest, 1000)
		if u.Status.Level != 2 || u.Status.StaminaMilliValue != c.want {
			t.Fatalf("stamina %d: level %d stamina %d, want level 2 stamina %d", c.before, u.Status.Level, u.Status.StaminaMilliValue, c.want)
		}
	}
}
