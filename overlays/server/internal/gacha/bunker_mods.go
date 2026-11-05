package gacha

// Pod Programs > Mods for summons (from the Lunar Tear Comfort Mod by
// NavHobbyDev, MIT).

import (
	"log"
	"math/rand"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/mods"
	"lunar-tear/server/internal/store"
)

// applyNoDuplicateFourStar, with No duplicate ★4 on, swaps each ★4 costume or
// weapon of a premium summon that the player already owns (or that an earlier
// slot of the same summon already gave) for one of the same kind they don't,
// from the same summon's pool. Once they own every ★4 of that kind, it stays.
// It runs before the summon is granted, so the result shows what arrives.
func (h *GachaHandler) applyNoDuplicateFourStar(user *store.UserState, entry store.GachaCatalogEntry, items []DrawnItem) {
	if entry.GachaLabelType != model.GachaLabelPremium || !mods.Get().NoDuplicateFourStar {
		return
	}
	bp := h.Pool.BannerPools[entry.GachaId]
	if bp == nil {
		bp = &masterdata.BannerPool{CostumesByRarity: h.Pool.CostumesByRarity, WeaponsByRarity: h.Pool.WeaponsByRarity}
	}
	swapDuplicateFourStars(user, items, bp, rand.Intn)
}

func swapDuplicateFourStars(user *store.UserState, items []DrawnItem, bp *masterdata.BannerPool, intn func(int) int) {
	owned := map[int32]map[int32]bool{
		int32(model.PossessionTypeCostume): {},
		int32(model.PossessionTypeWeapon):  {},
	}
	for _, c := range user.Costumes {
		owned[int32(model.PossessionTypeCostume)][c.CostumeId] = true
	}
	for _, w := range user.Weapons {
		owned[int32(model.PossessionTypeWeapon)][w.WeaponId] = true
	}
	for i, it := range items {
		have, kind := owned[it.PossessionType]
		if !kind || it.RarityType != model.RaritySSRare {
			continue
		}
		if have[it.PossessionId] {
			pool := bp.CostumesByRarity[model.RaritySSRare]
			if it.PossessionType == int32(model.PossessionTypeWeapon) {
				pool = bp.WeaponsByRarity[model.RaritySSRare]
			}
			var missing []masterdata.GachaPoolItem
			for _, p := range pool {
				if !have[p.PossessionId] {
					missing = append(missing, p)
				}
			}
			if len(missing) > 0 {
				p := missing[intn(len(missing))]
				log.Printf("[gacha] no duplicate ★4 (mod): %d -> %d", it.PossessionId, p.PossessionId)
				items[i].PossessionId, items[i].CharacterId = p.PossessionId, p.CharacterId
			}
		}
		have[items[i].PossessionId] = true
	}
}

// Medals become gems: every pityMedals summon medals become pityPaidGems paid
// gems and pityMomPoints Mama Points, sent to the gift box.
const (
	pityMedals    = 100
	pityPaidGems  = 1000
	pityMomPoints = 100
)

// applyPityRewards, with Medals become gems on, trades a summon's medals for
// gifts in whole hundreds, after the summon has added its medals.
func (h *GachaHandler) applyPityRewards(user *store.UserState, entry store.GachaCatalogEntry, nowMillis int64) {
	if !mods.Get().PityRewards || entry.MedalConsumableItemId == 0 {
		return
	}
	packs := user.ConsumableItems[entry.MedalConsumableItemId] / pityMedals
	if packs <= 0 {
		return
	}
	user.ConsumableItems[entry.MedalConsumableItemId] -= packs * pityMedals
	if bs, ok := user.Gacha.BannerStates[entry.GachaId]; ok {
		bs.MedalCount = max(bs.MedalCount-packs*pityMedals, 0)
		user.Gacha.BannerStates[entry.GachaId] = bs
	}
	for range packs {
		store.AddGift(user, model.PossessionTypePaidGem, 0, pityPaidGems, store.GiftTextSummons, nowMillis)
		if h.Config != nil && h.Config.ConsumableItemIdForMomPoint != 0 {
			store.AddGift(user, model.PossessionTypeConsumableItem, h.Config.ConsumableItemIdForMomPoint, pityMomPoints, store.GiftTextSummons, nowMillis)
		}
	}
	log.Printf("[gacha] medals become gems (mod): %d×%d medals of item %d -> gifts", packs, pityMedals, entry.MedalConsumableItemId)
}
