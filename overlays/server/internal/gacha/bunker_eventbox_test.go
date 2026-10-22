package gacha

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

func testEventBox() masterdata.EventSummon {
	return masterdata.EventSummon{Base: 340001, Levels: []masterdata.EventLevel{
		{Chance: 0.5, Items: []masterdata.BoxPrize{
			{Type: 2, Id: 330731, Count: 1, Stock: 1, Target: true, Main: true},
			{Type: 6, Id: 1, Count: 1000, Stock: 3},
		}},
		{Chance: 0.3, Items: []masterdata.BoxPrize{{Type: 6, Id: 1, Count: 5000, Stock: 2, Main: true}}},
	}}
}

var testUnlimited = []masterdata.BoxPrize{{Type: 5, Id: 100002, Count: 1}}

// A level's box runs out: no prize is drawn more often than its stock, and
// once the box is empty every draw is an unlimited one.
func TestEventBoxStockRunsOut(t *testing.T) {
	box := testEventBox()
	bs := store.GachaBannerState{}
	got := map[int32]int32{}
	for _, it := range drawEventBox(&bs, box, testUnlimited, 400) {
		got[it.PossessionId] += it.Count
	}
	if got[330731] != 1 || got[1] != 3000 || got[100002] != 396 {
		t.Fatalf("drawn: %v", got)
	}
}

// Drawing every target lets the player level up; the levels can't be skipped,
// and the last level is replenished only once it is empty.
func TestEventBoxLevelsUp(t *testing.T) {
	box := testEventBox()
	user := &store.UserState{}
	user.EnsureMaps()
	if err := resetEventBox(user, box); err == nil {
		t.Fatal("levelled up before drawing the main prize")
	}
	bs := user.Gacha.BannerStates[box.Base]
	for i := 0; i < 400 && !eventTargetsDrawn(bs, box); i++ {
		drawEventBox(&bs, box, testUnlimited, 1)
	}
	user.Gacha.BannerStates[box.Base] = bs
	if err := resetEventBox(user, box); err != nil {
		t.Fatal(err)
	}
	bs = user.Gacha.BannerStates[box.Base]
	if EventLevel(bs) != 2 || len(bs.BoxDrewCounts) != 0 {
		t.Fatalf("after levelling up: %+v", bs)
	}
	if err := resetEventBox(user, box); err == nil {
		t.Fatal("replenished the last level before it was empty")
	}
	for i := 0; i < 400; i++ {
		drawEventBox(&bs, box, testUnlimited, 1)
	}
	user.Gacha.BannerStates[box.Base] = bs
	if err := resetEventBox(user, box); err != nil {
		t.Fatal(err)
	}
	if bs = user.Gacha.BannerStates[box.Base]; EventLevel(bs) != 2 || len(bs.BoxDrewCounts) != 0 {
		t.Fatalf("after replenishing: %+v", bs)
	}
}
