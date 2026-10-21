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
