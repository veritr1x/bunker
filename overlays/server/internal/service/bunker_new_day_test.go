package service

import (
	"os"
	"path/filepath"
	"strconv"
	"testing"
	"time"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Start a new day resets dailies only: shop stock on a period of several days
// keeps counting whole days, while a daily period starts over at the press.
func TestMultiDayShopPeriodIgnoresPress(t *testing.T) {
	at := func(h int) int64 { return time.Date(2025, 3, 12, h, 0, 0, 0, gametime.Zone).UnixMilli() }
	three := masterdata.ShopStockReset{Type: masterdata.ShopAutoResetDaily, Period: 3}
	daily := masterdata.ShopStockReset{Type: masterdata.ShopAutoResetDaily, Period: 1}
	before, _ := shopStockPeriodStart(three, at(16))
	path := filepath.Join(t.TempDir(), "day-start.json")
	if err := os.WriteFile(path, []byte(`{"pressedRealMillis": `+strconv.FormatInt(at(15), 10)+`}`), 0o600); err != nil {
		t.Fatal(err)
	}
	gametime.SetDayStartPath(path)
	t.Cleanup(func() { gametime.SetDayStartPath("") })
	if got, _ := shopStockPeriodStart(three, at(16)); got != before {
		t.Fatalf("3-day period moved by a press: %d -> %d", before, got)
	}
	if got, _ := shopStockPeriodStart(daily, at(16)); got != at(15) {
		t.Fatalf("daily period starts at the press: %v", time.UnixMilli(got).In(gametime.Zone))
	}
}

// The game shows a daily-limited quest's plays left as its limit less
// DailyClearCount while LastClearDatetime is today; after Start a new day the
// clear before the press is yesterday's, so game start zeroes the count.
func TestGameStartZeroesDailyCountsBeforeTheDay(t *testing.T) {
	at := func(h int) int64 { return time.Date(2025, 3, 12, h, 0, 0, 0, gametime.Zone).UnixMilli() }
	path := filepath.Join(t.TempDir(), "day-start.json")
	if err := os.WriteFile(path, []byte(`{"pressedRealMillis": `+strconv.FormatInt(at(15), 10)+`}`), 0o600); err != nil {
		t.Fatal(err)
	}
	gametime.SetDayStartPath(path)
	t.Cleanup(func() { gametime.SetDayStartPath("") })
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	user.Quests[7] = store.UserQuestState{QuestId: 7, DailyClearCount: 3, LastClearDatetime: at(14)}
	user.Quests[8] = store.UserQuestState{QuestId: 8, DailyClearCount: 2, LastClearDatetime: at(16)}
	user.BigHuntStatuses[9] = store.BigHuntStatus{DailyChallengeCount: 2, LatestChallengeDatetime: at(14)}
	resetDailyCounts(user, at(17))
	if user.Quests[7].DailyClearCount != 0 || user.Quests[8].DailyClearCount != 2 || user.BigHuntStatuses[9].DailyChallengeCount != 0 {
		t.Fatalf("quests %+v %+v, big hunt %+v", user.Quests[7], user.Quests[8], user.BigHuntStatuses[9])
	}
}
