package service

import (
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
