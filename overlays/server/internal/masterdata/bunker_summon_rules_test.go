package masterdata

import (
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func basicEntry(id int32) store.GachaCatalogEntry {
	return store.GachaCatalogEntry{GachaId: id, GachaModeType: model.GachaModeBasic, GachaAutoResetType: model.GachaAutoResetNone,
		PricePhases: buildPremiumBasicPricePhases(id)}
}

func TestSummonRulePricesARegularSummon(t *testing.T) {
	rules := map[int32]summonRule{489: {Steps: []ruleStep{
		{Draws: 1, Price: 300, Cur: "gems"},
		{Draws: 10, Price: 3000, Cur: "paid", Limit: 5, Guar: "r3w"},
	}}}
	got := applySummonRules([]store.GachaCatalogEntry{basicEntry(489)}, rules)[0]
	if len(got.PricePhases) != 3 {
		t.Fatalf("phases: %+v", got.PricePhases)
	}
	one, ten, ticket := got.PricePhases[0], got.PricePhases[1], got.PricePhases[2]
	if one.PhaseId != 4891 || one.Price != 300 || one.PriceType != model.PriceTypeGem || one.DrawCount != 1 || one.FixedCount != 0 {
		t.Fatalf("single draw: %+v", one)
	}
	if ten.PhaseId != 4892 || ten.Price != 3000 || ten.PriceType != model.PriceTypePaidGem || ten.DrawCount != 10 ||
		ten.LimitExecCount != 5 || ten.FixedRarityMin != model.RaritySRare || ten.FixedCount != 1 {
		t.Fatalf("ten draws: %+v", ten)
	}
	// The premium ticket draw the game data gives a regular summon stays.
	if ticket.PhaseId != 4893 || ticket.PriceType != model.PriceTypeConsumableItem || ticket.PriceId != model.ConsumableIdPremiumTicket {
		t.Fatalf("ticket draw: %+v", ticket)
	}
}

func TestSummonRulePricesAStepUp(t *testing.T) {
	entry := store.GachaCatalogEntry{GachaId: 533001, GachaModeType: model.GachaModeStepup, MaxStepNumber: 5,
		PricePhases: buildStepUpPricePhases(533001, 5, nil)}
	rules := map[int32]summonRule{533001: {Steps: []ruleStep{
		{Step: 1, Draws: 10, Price: 3000, Cur: "paid", Guar: "r4w"},
		{Step: 2, Draws: 10, Price: 0, Cur: "free", Guar: "r3w"},
		{Step: 3, Draws: 10, Price: 3000, Cur: "paid", Guar: "r4c"},
	}}}
	got := applySummonRules([]store.GachaCatalogEntry{entry}, rules)[0]
	if got.MaxStepNumber != 3 || len(got.PricePhases) != 3 {
		t.Fatalf("steps: max %d, phases %+v", got.MaxStepNumber, got.PricePhases)
	}
	for i, p := range got.PricePhases {
		if p.StepNumber != int32(i+1) || p.LimitExecCount != 1 || p.PhaseId != 533001*10+int32(i+1) {
			t.Fatalf("step %d: %+v", i+1, p)
		}
	}
	if s2 := got.PricePhases[1]; s2.Price != 0 || s2.PriceType != model.PriceTypeGem {
		t.Fatalf("free step: %+v", s2)
	}
	if s1 := got.PricePhases[0]; s1.PriceType != model.PriceTypePaidGem || s1.FixedRarityMin != model.RaritySSRare || s1.FixedCount != 1 {
		t.Fatalf("step 1: %+v", s1)
	}
}

func TestSummonRuleOfTheWrongShapeIsIgnored(t *testing.T) {
	// Steps for a summon the game data has as a regular one (its step pages
	// have no art), and plain draws for a step-up: both keep their prices.
	basic := basicEntry(10)
	step := store.GachaCatalogEntry{GachaId: 11, GachaModeType: model.GachaModeStepup, MaxStepNumber: 5, PricePhases: buildStepUpPricePhases(11, 5, nil)}
	rules := map[int32]summonRule{
		10: {Steps: []ruleStep{{Step: 1, Draws: 10, Price: 1500, Cur: "paid"}}},
		11: {Steps: []ruleStep{{Draws: 10, Price: 3000, Cur: "gems"}}},
	}
	got := applySummonRules([]store.GachaCatalogEntry{basic, step}, rules)
	if got[0].PricePhases[1].Price != model.PremiumMultiPullPrice || got[1].MaxStepNumber != 5 || got[1].PricePhases[0].StepNumber != 1 {
		t.Fatalf("changed: %+v / %+v", got[0].PricePhases, got[1].PricePhases)
	}
}

func TestSummonRuleDailyAndGuarantees(t *testing.T) {
	rules := map[int32]summonRule{7: {Steps: []ruleStep{
		{Draws: 10, Price: 0, Cur: "free", Daily: true, Guar: "set10:feat"},
		{Draws: 10, Price: 3000, Cur: "gems", Guar: "none"},
	}}}
	got := applySummonRules([]store.GachaCatalogEntry{basicEntry(7)}, rules)[0]
	if got.GachaAutoResetType != model.GachaAutoResetDaily || got.GachaAutoResetPeriod != 1 {
		t.Fatalf("daily: %+v", got)
	}
	if p := got.PricePhases[0]; p.LimitExecCount != 1 || p.FixedRarityMin != model.RaritySSRare || p.FixedCount != 1 {
		t.Fatalf("daily free ★4: %+v", p)
	}
	if p := got.PricePhases[1]; p.FixedCount != 0 {
		t.Fatalf("nothing guaranteed: %+v", p)
	}
}

func TestEmbeddedSummonRulesAreValid(t *testing.T) {
	rules, err := loadSummonRules()
	if err != nil {
		t.Fatal(err)
	}
	if len(rules) < 150 {
		t.Fatalf("only %d summon rules", len(rules))
	}
	for id, r := range rules {
		if len(r.Steps) == 0 || len(r.Steps) > 9 {
			t.Fatalf("summon %d: %d steps", id, len(r.Steps))
		}
		stepped := r.Steps[0].Step > 0
		for i, s := range r.Steps {
			if s.Draws <= 0 || s.Price < 0 || priceTypeOf(s.Cur) == model.PriceTypeUnknown {
				t.Fatalf("summon %d step %d: %+v", id, i, s)
			}
			if stepped && s.Step != int32(i+1) {
				t.Fatalf("summon %d: steps out of order: %+v", id, r.Steps)
			}
		}
	}
}
