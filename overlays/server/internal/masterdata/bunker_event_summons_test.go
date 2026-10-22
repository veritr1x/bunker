package masterdata

import (
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func testEventFile() eventSummonsFile {
	return eventSummonsFile{
		Unlimited: []BoxPrize{{Type: 5, Id: 100002, Count: 1}},
		Events: []EventSummon{{
			Chapter: 340, Base: 340001, Assets: []string{"event_340_01", "event_340_02"}, Tickets: []int32{6071},
			Levels: []EventLevel{
				{Chance: 0.35, Items: []BoxPrize{{Type: 2, Id: 330731, Count: 1, Stock: 1, Target: true, Main: true}, {Type: 6, Id: 1, Count: 1000, Stock: 30}}},
				{Chance: 0.30, Items: []BoxPrize{{Type: 6, Id: 1, Count: 5000, Stock: 50, Main: true}}},
			},
		}},
	}
}

// Each event's summon is one Event-tab box summon on the Summons screen,
// open from the event's start until two days after it ends (the notices: the
// Event Summons can be used until two days after the event period ends),
// drawn with any of its tickets, one or ten at a time.
func TestEventSummonsJoinTheCatalog(t *testing.T) {
	chapters := map[int32]EntityMEventQuestChapter{340: {EventQuestChapterId: 340, StartDatetime: 1_000_000, EndDatetime: 2_000_000}}
	got := addEventSummons(nil, testEventFile(), chapters)
	if len(got) != 1 {
		t.Fatalf("%d entries", len(got))
	}
	e := got[0]
	if e.GachaId != 340001 || e.GachaLabelType != model.GachaLabelEvent || e.GachaModeType != model.GachaModeBox || e.GroupId != 340001 ||
		e.BannerAssetName != "event_340_01" || e.StartDatetime != 1_000_000 || e.EndDatetime != 2_000_000+2*24*3600*1000 {
		t.Fatalf("event summon: %+v", e)
	}
	if len(e.PricePhases) != 2 || e.PricePhases[0].PriceType != model.PriceTypeConsumableItem || e.PricePhases[0].PriceId != 6071 ||
		e.PricePhases[0].DrawCount != 1 || e.PricePhases[1].DrawCount != 10 || e.PricePhases[1].Price != 10 {
		t.Fatalf("event summon prices: %+v", e.PricePhases)
	}
}

// Its levels have ids of their own (340001, 340002, ...), all one summon.
func TestEventSummonLevelIds(t *testing.T) {
	setEventSummons(testEventFile())
	defer setEventSummons(eventSummonsFile{})
	for id, want := range map[int32]int32{340001: 1, 340002: 2} {
		box, level, ok := EventSummonFor(id)
		if !ok || box.Base != 340001 || level != want {
			t.Fatalf("%d: level %d ok %v", id, level, ok)
		}
	}
	if _, _, ok := EventSummonFor(340003); ok {
		t.Fatal("a level past the last one")
	}
	if _, _, ok := EventSummonFor(store.GachaCatalogEntry{}.GachaId); ok {
		t.Fatal("id 0")
	}
}

// The embedded file is the compiled data and holds every event.
func TestEmbeddedEventSummonsAreValid(t *testing.T) {
	f, err := loadEventSummonsFile()
	if err != nil {
		t.Fatal(err)
	}
	if len(f.Events) < 30 || len(f.Unlimited) == 0 {
		t.Fatalf("%d events, %d unlimited", len(f.Events), len(f.Unlimited))
	}
	for _, e := range f.Events {
		if len(e.Levels) != len(e.Assets) || len(e.Tickets) == 0 {
			t.Fatalf("event %d: %d levels, %d assets, tickets %v", e.Chapter, len(e.Levels), len(e.Assets), e.Tickets)
		}
		last := e.Levels[len(e.Levels)-1]
		for _, it := range last.Items {
			if it.Target {
				t.Fatalf("event %d: the last level replenishes; it has no main-prize targets", e.Chapter)
			}
		}
		for i, l := range e.Levels[:len(e.Levels)-1] {
			targets := 0
			for _, it := range l.Items {
				if it.Target {
					targets++
				}
			}
			if targets == 0 {
				t.Fatalf("event %d level %d has nothing to level up with", e.Chapter, i+1)
			}
		}
	}
}
