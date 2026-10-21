package gacha

import (
	"math/rand"
	"strings"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// applyOwnedRules gives "a ★★★★ character you don't own" in the guaranteed
// slots: one of the listed set (or any ★4 character) the player hasn't got.
// If the player owns them all, the slot stays as drawn.
func applyOwnedRules(user *store.UserState, items []DrawnItem, bp *masterdata.BannerPool, pool *masterdata.GachaCatalog, rule masterdata.PhaseRule, fixedCount int) {
	if !strings.HasPrefix(rule.Guar, "r4c_unowned") && rule.Guar != "set_unowned" {
		return
	}
	owned := map[int32]bool{}
	for _, c := range user.Costumes {
		owned[c.CostumeId] = true
	}
	var candidates []masterdata.GachaPoolItem
	if len(rule.Set) > 0 {
		for _, id := range rule.Set {
			if c, ok := pool.CostumeById[id]; ok && !owned[id] {
				candidates = append(candidates, c)
			}
		}
	} else {
		for _, c := range bp.CostumesByRarity[model.RaritySSRare] {
			if !owned[c.PossessionId] {
				candidates = append(candidates, c)
			}
		}
	}
	if len(candidates) == 0 {
		return
	}
	for i := max(len(items)-fixedCount, 0); i < len(items); i++ {
		if items[i].PossessionType == int32(model.PossessionTypeCostume) && items[i].RarityType >= model.RaritySSRare && !owned[items[i].PossessionId] {
			continue
		}
		pick := candidates[rand.Intn(len(candidates))]
		items[i] = DrawnItem{PossessionType: pick.PossessionType, PossessionId: pick.PossessionId, RarityType: pick.RarityType, CharacterId: pick.CharacterId}
	}
}

// awakenGranted brings the ★★★★ characters a draw gave to awakening level 5
// when its rule says they arrive awakened ("Max Awakening" summons).
func awakenGranted(user *store.UserState, items []DrawnItem, rule masterdata.PhaseRule) {
	if rule.Guar != "set_awakened5" {
		return
	}
	drawn := map[int32]bool{}
	for _, it := range items {
		if it.PossessionType == int32(model.PossessionTypeCostume) && it.RarityType >= model.RaritySSRare {
			drawn[it.PossessionId] = true
		}
	}
	for k, c := range user.Costumes {
		if drawn[c.CostumeId] && c.AwakenCount < 5 {
			c.AwakenCount = 5
			user.Costumes[k] = c
		}
	}
}
