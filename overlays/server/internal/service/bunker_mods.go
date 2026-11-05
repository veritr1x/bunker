package service

// Pod Programs > Mods for the shop and the home field (from the Lunar Tear
// Comfort Mod by NavHobbyDev, MIT).

import (
	"math/rand"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/mods"
)

// modUnlimitedStock reports a shop item whose stock restocks daily, weekly or
// monthly (ShopAutoResetDaily with any period, ShopAutoResetMonthly) while
// Unlimited shop stock is on: buying it does not count against its stock.
// Items with a lifetime limit keep it. The game shows the stock left as the
// limit minus what was bought, so it stays full.
func modUnlimitedStock(catalog *masterdata.ShopCatalog, item masterdata.EntityMShopItem) bool {
	if item.ShopItemLimitedStockId <= 0 || !mods.Get().ShopUnlimited {
		return false
	}
	reset, ok := catalog.LimitedStockReset[item.ShopItemLimitedStockId]
	return ok && (reset.Type == masterdata.ShopAutoResetDaily || reset.Type == masterdata.ShopAutoResetMonthly)
}

// lostItemGems are the free gems a Lost Item gives with Lost Items give gems
// on, and how often each amount comes up (the Comfort Mod's weights).
var lostItemGems = []struct{ count, weight int32 }{{100, 25000}, {250, 10000}, {500, 500}, {1000, 1}}

// lostItemDrop is what a per-tap drop on the home field gives: free gems for a
// Lost Item (types 2 and 8) with Lost Items give gems on, otherwise cageDrop.
func lostItemDrop(gimmickType model.GimmickType) (model.PossessionType, int32, int32) {
	if gimmickType != model.GimmickTypeCageIntervalDropItem && gimmickType != model.GimmickTypeMapOnlyCageIntervalDrop || !mods.Get().LostItemGems {
		return cageDrop()
	}
	return model.PossessionTypeFreeGem, 0, pickLostItemGems(rand.Int31n)
}

func pickLostItemGems(intn func(int32) int32) int32 {
	var total int32
	for _, g := range lostItemGems {
		total += g.weight
	}
	roll := intn(total)
	for _, g := range lostItemGems {
		if roll < g.weight {
			return g.count
		}
		roll -= g.weight
	}
	return lostItemGems[0].count
}
