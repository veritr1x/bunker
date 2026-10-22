package service

import (
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func eventSummonEntry() store.GachaCatalogEntry {
	masterdata.SetEventSummonsForTest([]masterdata.EventSummon{{
		Chapter: 340, Base: 340001, Assets: []string{"event_340_01", "event_340_02"}, Tickets: []int32{6071},
		Levels: []masterdata.EventLevel{
			{Chance: 0.35, Items: []masterdata.BoxPrize{
				{Type: 2, Id: 330731, Count: 1, Stock: 1, Target: true, Main: true},
				{Type: 6, Id: 1, Count: 1000, Stock: 30},
			}},
			{Chance: 0.30, Items: []masterdata.BoxPrize{{Type: 6, Id: 1, Count: 5000, Stock: 50, Main: true}}},
		},
	}}, nil)
	return store.GachaCatalogEntry{
		GachaId: 340001, GachaLabelType: model.GachaLabelEvent, GachaModeType: model.GachaModeBox, GroupId: 340001,
		BannerAssetName: "event_340_01", IsUserGachaUnlock: true,
		PricePhases: []store.GachaPricePhaseEntry{{PhaseId: 3400011, PriceType: model.PriceTypeConsumableItem, PriceId: 6071, Price: 1, DrawCount: 1}},
	}
}

// The client builds an event summon from one Gacha per level, grouped by
// GachaBoxGroupId, all with the player's level as CurrentBoxNumber
// (CalculatorGacha.CreateEventGacha); each level shows its main prizes.
func TestEventSummonIsOneGachaPerLevel(t *testing.T) {
	entry := eventSummonEntry()
	defer masterdata.SetEventSummonsForTest(nil, nil)
	user := store.UserState{}
	user.EnsureMaps()
	bs := store.GachaBannerState{GachaId: 340001, BoxNumber: 1, BoxDrewCounts: map[int32]int32{0: 1}}
	got := protoGachas(entry, &bs, user)
	if len(got) != 2 {
		t.Fatalf("%d gachas", len(got))
	}
	for i, g := range got {
		box := g.GachaMode.(*pb.Gacha_GachaModeBoxComposition).GachaModeBoxComposition
		if g.GachaId != 340001+int32(i) || box.BoxNumber != int32(i+1) || box.CurrentBoxNumber != 1 || box.GachaBoxGroupId != 340001 ||
			box.GachaAssetName != entry.BannerAssetName[:len("event_340_")]+[]string{"01", "02"}[i] {
			t.Fatalf("level %d: gacha %d box %+v", i+1, g.GachaId, box)
		}
	}
	lv1 := got[0].GachaMode.(*pb.Gacha_GachaModeBoxComposition).GachaModeBoxComposition
	if len(lv1.PromotionGachaOddsItem) != 1 {
		t.Fatalf("level 1 main prizes: %+v", lv1.PromotionGachaOddsItem)
	}
	p := lv1.PromotionGachaOddsItem[0]
	if p.GachaItem.PossessionId != 330731 || p.MaxDrawableCount != 1 || p.DrewCount != 1 || !p.IsTarget {
		t.Fatalf("main prize: %+v", p)
	}
	if !lv1.IsCurrentBoxResettable || !lv1.IsResettableByDrawingAllTargets {
		t.Fatal("Level Up not offered with every target drawn")
	}
	if e, _ := resolveGachaId([]store.GachaCatalogEntry{entry}, 340002); e == nil || e.GachaId != 340001 {
		t.Fatalf("level 2's id resolves to %+v", e)
	}
}

// On the game data: every event with an event summon has one, on its event's
// dates, and Blazing Binding Oculus (2024-01) draws with its ticket.
func TestEventSummonsOnTheGameData(t *testing.T) {
	byId, handler := catalogById(t)
	e, ok := byId[340001]
	if !ok {
		t.Fatal("Blazing Binding Oculus summon 340001 missing")
	}
	if e.GachaLabelType != model.GachaLabelEvent || e.StartDatetime != 1706666400000 || e.EndDatetime != 1708221599000+2*24*3600*1000 {
		t.Fatalf("340001: label %d %d-%d", e.GachaLabelType, e.StartDatetime, e.EndDatetime)
	}
	events := 0
	for _, x := range byId {
		if x.GachaLabelType == model.GachaLabelEvent && x.GachaModeType == model.GachaModeBox {
			events++
		}
	}
	if events < 30 {
		t.Fatalf("%d event summons", events)
	}
	u := store.UserState{}
	u.EnsureMaps()
	u.ConsumableItems[6071] = 20
	res, err := handler.HandleDraw(&u, e, e.PricePhases[1].PhaseId, 1) // a 10-draw
	if err != nil {
		t.Fatal(err)
	}
	if len(res.Items) != 10 || u.ConsumableItems[6071] != 10 {
		t.Fatalf("10-draw: %d items, %d tickets left", len(res.Items), u.ConsumableItems[6071])
	}
}
