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
