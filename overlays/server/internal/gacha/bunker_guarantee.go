package gacha

import (
	"math/rand"
	"strings"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
)

// ruleRate is a draw's ★4 rate multiplier: its rule's (none if the rule has
// no rate-up), or the step-up boost for summons without rules.
func ruleRate(rule masterdata.PhaseRule, ruled bool, fallback float64) float64 {
	if !ruled {
		return fallback
	}
	if rule.Rate > 0 {
		return rule.Rate
	}
	return 1
}

// applyGuarantee makes the guaranteed slots (the last fixedCount) meet the
// draw's rule: the featured character, one of a listed set, a ★4 character
// or a ★4 weapon. A slot that already meets it stays; otherwise it is drawn
// again from what the rule allows. Rarity-only rules (r3w, r4) are left to
// the slot's minimum rarity.
func applyGuarantee(items []DrawnItem, bp *masterdata.BannerPool, pool *masterdata.GachaCatalog, rule masterdata.PhaseRule, fixedCount int) {
	if rule.Feat4 {
		featureEveryFourStar(items, bp)
	}
	allowed := guaranteeCandidates(bp, pool, rule)
	if len(allowed) == 0 || fixedCount <= 0 {
		return
	}
	in := make(map[int32]bool, len(allowed))
	for _, a := range allowed {
		in[a.PossessionId] = true
	}
	for i := max(len(items)-fixedCount, 0); i < len(items); i++ {
		if in[items[i].PossessionId] {
			continue
		}
		pick := allowed[rand.Intn(len(allowed))]
		items[i] = DrawnItem{PossessionType: pick.PossessionType, PossessionId: pick.PossessionId, RarityType: pick.RarityType, CharacterId: pick.CharacterId}
	}
}

func guaranteeCandidates(bp *masterdata.BannerPool, pool *masterdata.GachaCatalog, rule masterdata.PhaseRule) []masterdata.GachaPoolItem {
	g := rule.Guar
	ssrCostumes := bp.CostumesByRarity[model.RaritySSRare]
	var featured []masterdata.GachaPoolItem
	for _, f := range bp.Featured {
		if f.PossessionType == int32(model.PossessionTypeCostume) && f.RarityType >= model.RaritySSRare {
			featured = append(featured, f)
		}
	}
	var set []masterdata.GachaPoolItem
	for _, id := range rule.Set {
		if c, ok := pool.CostumeById[id]; ok {
			set = append(set, c)
		}
	}
	or := func(lists ...[]masterdata.GachaPoolItem) []masterdata.GachaPoolItem {
		for _, l := range lists {
			if len(l) > 0 {
				return l
			}
		}
		return nil
	}
	switch {
	case g == "" || g == "none" || strings.HasPrefix(g, "r3") || g == "r4" || strings.HasPrefix(g, "r4:"):
		return nil
	case strings.HasPrefix(g, "r4w"):
		return bp.WeaponsByRarity[model.RaritySSRare]
	case g == "r4c_feat" || g == "set10:feat":
		return or(featured, ssrCostumes)
	case strings.HasPrefix(g, "set10:feat+"):
		return or(append(append([]masterdata.GachaPoolItem(nil), featured...), set...), ssrCostumes)
	case strings.HasPrefix(g, "set"):
		return or(set, ssrCostumes)
	case strings.HasPrefix(g, "r4c"):
		return ssrCostumes
	}
	return nil
}

// featureEveryFourStar makes every ★4 drawn a featured one, as the paid-only
// summons promised ("all ★★★★ weapons that appear are guaranteed to be
// featured weapons"): a ★4 character becomes a featured character, a ★4
// weapon a featured weapon. A kind with nothing featured stays as drawn.
func featureEveryFourStar(items []DrawnItem, bp *masterdata.BannerPool) {
	byType := map[int32][]masterdata.GachaPoolItem{}
	in := map[int32]bool{}
	for _, f := range bp.Featured {
		if f.RarityType >= model.RaritySSRare {
			byType[f.PossessionType] = append(byType[f.PossessionType], f)
			in[f.PossessionId] = true
		}
	}
	for i, it := range items {
		pool := byType[it.PossessionType]
		if it.RarityType < model.RaritySSRare || in[it.PossessionId] || len(pool) == 0 {
			continue
		}
		pick := pool[rand.Intn(len(pool))]
		items[i] = DrawnItem{PossessionType: pick.PossessionType, PossessionId: pick.PossessionId, RarityType: pick.RarityType, CharacterId: pick.CharacterId}
	}
}
