package service

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

func TestGuerrillaUnlockIsFreeOnceADayThenCostsGems(t *testing.T) {
	const day = int64(24 * 60 * 60 * 1000)
	dayStart := int64(1793000000000)
	user := &store.UserState{}
	user.Gem.FreeGem, user.Gem.PaidGem = 150, 1000

	// The day's free unlock.
	if err := openGuerrilla(user, dayStart+1000, dayStart, 1, 100, 60); err != nil {
		t.Fatal(err)
	}
	if user.Gem.FreeGem != 150 || user.GuerrillaFreeOpen.DailyOpenedCount != 1 || user.GuerrillaFreeOpen.OpenMinutes != 60 {
		t.Fatalf("free unlock: %+v %+v", user.Gem, user.GuerrillaFreeOpen)
	}
	// Then 100 gems, free gems first.
	if err := openGuerrilla(user, dayStart+5000, dayStart, 1, 100, 60); err != nil {
		t.Fatal(err)
	}
	if user.Gem.FreeGem != 50 || user.Gem.PaidGem != 1000 || user.GuerrillaFreeOpen.DailyOpenedCount != 2 {
		t.Fatalf("paid unlock: %+v %+v", user.Gem, user.GuerrillaFreeOpen)
	}
	if user.GuerrillaFreeOpen.StartDatetime != dayStart+5000 {
		t.Fatalf("not reopened: %+v", user.GuerrillaFreeOpen)
	}
	// Not enough gems: nothing changes.
	user.Gem.FreeGem, user.Gem.PaidGem = 20, 30
	before := user.GuerrillaFreeOpen
	if err := openGuerrilla(user, dayStart+9000, dayStart, 1, 100, 60); err == nil {
		t.Fatal("opened without enough gems")
	}
	if user.GuerrillaFreeOpen != before || user.Gem.FreeGem != 20 || user.Gem.PaidGem != 30 {
		t.Fatalf("changed on refusal: %+v %+v", user.Gem, user.GuerrillaFreeOpen)
	}
	// The next day the free unlock is back.
	if err := openGuerrilla(user, dayStart+day+1000, dayStart+day, 1, 100, 60); err != nil {
		t.Fatal(err)
	}
	if user.Gem.FreeGem != 20 || user.Gem.PaidGem != 30 || user.GuerrillaFreeOpen.DailyOpenedCount != 1 {
		t.Fatalf("next day: %+v %+v", user.Gem, user.GuerrillaFreeOpen)
	}
}

func TestGuerrillaUnlockNeedsAnUnlockRowInItsTerm(t *testing.T) {
	rows := []masterdata.EntityMEventQuestGuerrillaFreeOpen{
		{EventQuestGuerrillaFreeOpenId: 1, OpenMinutes: 60, DailyOpenMaxCount: 1, StartDatetime: 1000, EndDatetime: 5000},
	}
	if _, _, ok := guerrillaTerm(rows, 999); ok {
		t.Fatal("open before the unlock's start (the calendar has not reached it)")
	}
	if free, minutes, ok := guerrillaTerm(rows, 1000); !ok || free != 1 || minutes != 60 {
		t.Fatalf("at the start: %d %d %v", free, minutes, ok)
	}
	if _, _, ok := guerrillaTerm(rows, 5000); ok {
		t.Fatal("open after the end")
	}
	if _, _, ok := guerrillaTerm(nil, 1000); ok {
		t.Fatal("open without a row")
	}
}
