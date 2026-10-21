package service

import (
	"math"
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func detailsPool() *masterdata.BannerPool {
	item := func(t model.PossessionType, id, rarity int32, char int32) masterdata.GachaPoolItem {
		return masterdata.GachaPoolItem{PossessionType: int32(t), PossessionId: id, RarityType: rarity, CharacterId: char}
	}
	return &masterdata.BannerPool{
		CostumesByRarity: map[int32][]masterdata.GachaPoolItem{
			model.RaritySSRare: {item(model.PossessionTypeCostume, 1001, model.RaritySSRare, 1), item(model.PossessionTypeCostume, 1002, model.RaritySSRare, 2)},
			model.RaritySRare:  {item(model.PossessionTypeCostume, 1101, model.RaritySRare, 3)},
		},
		WeaponsByRarity: map[int32][]masterdata.GachaPoolItem{
			model.RaritySSRare: {item(model.PossessionTypeWeapon, 2001, model.RaritySSRare, 0)},
			model.RaritySRare:  {item(model.PossessionTypeWeapon, 2101, model.RaritySRare, 0)},
			model.RarityRare:   {item(model.PossessionTypeWeapon, 2201, model.RarityRare, 0)},
		},
	}
}

func ratesById(rates []itemRate) map[int32]float64 {
	out := map[int32]float64{}
	for _, r := range rates {
		out[r.item.PossessionId] += r.percent
	}
	return out
}

// A ★4-guaranteed ticket summon (970001): every draw is the guaranteed slot,
// so the page lists only ★4 items, shared the way the ★4 tiers are weighted.
func TestGuaranteedSlotRatesOnlyListTheGuaranteedRarity(t *testing.T) {
	got := ratesById(slotRates(detailsPool(), model.RaritySSRare, nil))
	// Default ★4: 2% costume (two costumes), 3% weapon (one weapon).
	want := map[int32]float64{1001: 20, 1002: 20, 2001: 60}
	if len(got) != len(want) {
		t.Fatalf("rates %v, want %v", got, want)
	}
	for id, p := range want {
		if math.Abs(got[id]-p) > 1e-9 {
			t.Fatalf("item %d: %.4f%%, want %.4f%% (all %v)", id, got[id], p, got)
		}
	}
}

// A guarantee that names what the slot may give (an element, a set) replaces
// anything else evenly from that list.
func TestGuaranteedSlotRatesWithCandidates(t *testing.T) {
	bp := detailsPool()
	only := []masterdata.GachaPoolItem{bp.CostumesByRarity[model.RaritySSRare][1]}
	got := ratesById(slotRates(bp, model.RaritySSRare, only))
	if len(got) != 1 || math.Abs(got[1002]-100) > 1e-9 {
		t.Fatalf("rates %v, want only 1002 at 100%%", got)
	}
}

// Ticket summons have no dates of their own (no banner row in the original
// data); the page says they stay open instead of showing a 2099 end.
func TestPeriodWithoutAnEnd(t *testing.T) {
	ticket := store.GachaCatalogEntry{StartDatetime: 1627437600000, EndDatetime: 4102444799000}
	if got := periodHTML(ticket, true); got != "<p class=k>From 2021/07/28 (UTC) · no end date: open while you have a ticket</p>" {
		t.Fatalf("ticket summon period: %s", got)
	}
	parked := store.GachaCatalogEntry{StartDatetime: 1627437600000, EndDatetime: 4102185600000}
	if got := periodHTML(parked, false); got != "<p class=k>From 2021/07/28 (UTC) · no end date</p>" {
		t.Fatalf("open-ended summon period: %s", got)
	}
	dated := store.GachaCatalogEntry{StartDatetime: 1627437600000, EndDatetime: 1628042400000}
	if got := periodHTML(dated, false); got != "<p class=k>2021/07/28 – 2021/08/04 (UTC)</p>" {
		t.Fatalf("dated summon period: %s", got)
	}
}
