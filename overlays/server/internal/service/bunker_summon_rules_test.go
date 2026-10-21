package service

import (
	"testing"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// With the original game data: a step-up whose notice guarantees its
// featured character on a step gives one on that step every time round.
func TestFeaturedCharacterGuaranteeOnTheGameData(t *testing.T) {
	byId, handler := catalogById(t)
	cats := loadMaster(t).Get()
	for _, e := range byId {
		bp := cats.GachaPool.BannerPools[e.GachaId]
		if e.GachaModeType != model.GachaModeStepup || bp == nil {
			continue
		}
		featured := map[int32]bool{}
		for _, f := range bp.Featured {
			if f.PossessionType == int32(model.PossessionTypeCostume) {
				featured[f.PossessionId] = true
			}
		}
		guaranteed := map[int32]bool{}
		for _, p := range e.PricePhases {
			if rule, ok := masterdata.PhaseRuleFor(p.PhaseId); ok && (rule.Guar == "set10:feat" || rule.Guar == "r4c_feat") {
				guaranteed[p.PhaseId] = true
			}
		}
		if len(featured) == 0 || len(guaranteed) == 0 {
			continue
		}
		defer gametime.SetCalendar(nil)
		at := e.StartDatetime + 3600_000
		gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: 1, JumpMillis: at - gametime.Now().UnixMilli(), Speed: 1})
		u := store.UserState{}
		u.EnsureMaps()
		u.Gem.PaidGem, u.Gem.FreeGem = 10_000_000, 10_000_000
		checked := 0
		for round := 0; round < 10; round++ {
			for _, p := range e.PricePhases {
				res, err := handler.HandleDraw(&u, e, p.PhaseId, 1)
				if err != nil {
					t.Fatalf("summon %d step %d round %d: %v", e.GachaId, p.StepNumber, round, err)
				}
				if guaranteed[p.PhaseId] {
					last := res.Items[len(res.Items)-1]
					if !featured[last.PossessionId] {
						t.Fatalf("summon %d step %d: guaranteed slot %+v is not a featured character %v", e.GachaId, p.StepNumber, last, featured)
					}
					checked++
				}
			}
		}
		t.Logf("summon %d: %d guaranteed draws, all featured", e.GachaId, checked)
		return
	}
	t.Skip("no step-up with a featured-character guarantee in this game data")
}

// A step's bonus items (here from its notice) reach the player.
func TestStepBonusItemsAreGranted(t *testing.T) {
	byId, handler := catalogById(t)
	for _, e := range byId {
		if e.GachaModeType != model.GachaModeStepup || len(e.PricePhases) == 0 || len(e.PricePhases[0].Bonuses) == 0 {
			continue
		}
		defer gametime.SetCalendar(nil)
		at := e.StartDatetime + 3600_000
		gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: 1, JumpMillis: at - gametime.Now().UnixMilli(), Speed: 1})
		u := store.UserState{}
		u.EnsureMaps()
		u.Gem.PaidGem, u.Gem.FreeGem = 1_000_000, 1_000_000
		if _, err := handler.HandleDraw(&u, e, e.PricePhases[0].PhaseId, 1); err != nil {
			t.Fatalf("summon %d step 1: %v", e.GachaId, err)
		}
		for _, b := range e.PricePhases[0].Bonuses {
			var have int32
			switch model.PossessionType(b.PossessionType) {
			case model.PossessionTypeMaterial:
				have = u.Materials[b.PossessionId]
			case model.PossessionTypeConsumableItem:
				have = u.ConsumableItems[b.PossessionId]
			}
			if have < b.Count {
				t.Fatalf("summon %d step 1 bonus %+v: player has %d", e.GachaId, b, have)
			}
		}
		t.Logf("summon %d step 1 gave %+v", e.GachaId, e.PricePhases[0].Bonuses)
		return
	}
	t.Skip("no step-up with bonus items in this game data")
}

// With the original game data: the paid-only twins are summons, with their
// regular summon's lineup and a link to their notice.
func TestPaidTwinsOnTheGameData(t *testing.T) {
	byId, _ := catalogById(t)
	cats := loadMaster(t).Get()
	twin, ok := byId[490] // Paid Only: Abstract Belle Summons
	if !ok {
		t.Fatal("summon 490 (Paid Only: Abstract Belle) missing")
	}
	if twin.BannerAssetName != "limited_490" || twin.InformationId != 1078 || twin.PricePhases[0].PriceType != model.PriceTypePaidGem {
		t.Fatalf("twin: %+v", twin)
	}
	a, b := cats.GachaPool.BannerPools[489], cats.GachaPool.BannerPools[490]
	if a == nil || b == nil || len(b.Featured) == 0 || len(a.Featured) != len(b.Featured) || a.Featured[0] != b.Featured[0] {
		t.Fatalf("twin lineup differs from Abstract Belle's: %+v vs %+v", a, b)
	}
	twins := 0
	for id, e := range byId {
		if e.InformationId != 0 && e.GachaMedalId == 0 && id > 400 {
			twins++
		}
	}
	t.Logf("summon 490 ok; %d summons link straight to a notice", twins)
}

// With the original game data: the Fire ★★★★ Guaranteed ticket summon gives
// a fire ★★★★ every time, for one Fire ★★★★ Guaranteed Summons Ticket.
func TestFireTicketSummonOnTheGameData(t *testing.T) {
	byId, handler := catalogById(t)
	e, ok := byId[970003]
	if !ok {
		t.Fatal("Fire ★★★★ Guaranteed Summons missing")
	}
	u := store.UserState{}
	u.EnsureMaps()
	u.ConsumableItems[1205] = 20
	for i := 0; i < 20; i++ {
		res, err := handler.HandleDraw(&u, e, e.PricePhases[0].PhaseId, 1)
		if err != nil {
			t.Fatalf("draw %d: %v", i, err)
		}
		it := res.Items[0]
		pi := masterdata.GachaPoolItem{PossessionType: it.PossessionType, PossessionId: it.PossessionId}
		if it.RarityType != model.RaritySSRare || masterdata.ElementOf(pi) != 2 {
			t.Fatalf("draw %d gave %+v (element %d)", i, it, masterdata.ElementOf(pi))
		}
	}
	if u.ConsumableItems[1205] != 0 {
		t.Fatalf("tickets left: %d", u.ConsumableItems[1205])
	}
}
