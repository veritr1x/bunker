package service

import (
	"os"
	"path/filepath"
	"strconv"
	"testing"
	"time"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func TestFreeSummonBadge(t *testing.T) {
	now := int64(1_800_000_000_000)
	free := store.GachaCatalogEntry{GachaId: 9, GachaAutoResetType: model.GachaAutoResetDaily, EndDatetime: now + 10*86400000,
		PricePhases: []store.GachaPricePhaseEntry{{PhaseId: 901, Price: 0, LimitExecCount: 1}}}
	paid := store.GachaCatalogEntry{GachaId: 8, PricePhases: []store.GachaPricePhaseEntry{{PhaseId: 801, Price: 3000}}}
	user := &store.UserState{}
	user.Ext.GachaExec = map[int32]store.GachaExecState{}

	badges := freeSummonBadges([]store.GachaCatalogEntry{free, paid}, user, now)
	if len(badges) != 1 || badges[0].DisplayStartDatetime.AsTime().UnixMilli() > now || badges[0].DisplayEndDatetime.AsTime().UnixMilli() != free.EndDatetime {
		t.Fatalf("unused free draw: %v", badges)
	}
	// Used today: the badge comes back at the next daily reset.
	user.Ext.GachaExec[901] = store.GachaExecState{Day: gametime.StartOfDay(now), Count: 1}
	badges = freeSummonBadges([]store.GachaCatalogEntry{free, paid}, user, now)
	next := gametime.StartOfDay(now) + int64(24*time.Hour/time.Millisecond)
	if len(badges) != 1 || badges[0].DisplayStartDatetime.AsTime().UnixMilli() != next {
		t.Fatalf("used free draw: %v", badges)
	}
}

// After Start a new day the used draw comes back at the next real daily reset
// (midnight GMT-8), not a day after the press.
func TestFreeSummonBadgeAfterNewDay(t *testing.T) {
	at := func(h int) int64 { return time.Date(2025, 3, 12, h, 0, 0, 0, gametime.Zone).UnixMilli() }
	path := filepath.Join(t.TempDir(), "day-start.json")
	if err := os.WriteFile(path, []byte(`{"pressedRealMillis": `+strconv.FormatInt(at(15), 10)+`}`), 0o600); err != nil {
		t.Fatal(err)
	}
	gametime.SetDayStartPath(path)
	t.Cleanup(func() { gametime.SetDayStartPath("") })
	now := at(16)
	free := store.GachaCatalogEntry{GachaId: 9, GachaAutoResetType: model.GachaAutoResetDaily, EndDatetime: at(24 * 10),
		PricePhases: []store.GachaPricePhaseEntry{{PhaseId: 901, Price: 0, LimitExecCount: 1}}}
	user := &store.UserState{}
	user.Ext.GachaExec = map[int32]store.GachaExecState{901: {Day: gametime.StartOfDay(now), Count: 1}}
	badges := freeSummonBadges([]store.GachaCatalogEntry{free}, user, now)
	if len(badges) != 1 || badges[0].DisplayStartDatetime.AsTime().UnixMilli() != at(24) {
		t.Fatalf("badge from %v, want the next midnight", badges[0].DisplayStartDatetime.AsTime().In(gametime.Zone))
	}
}
