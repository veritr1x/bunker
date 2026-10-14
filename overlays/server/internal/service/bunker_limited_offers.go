package service

import (
	"fmt"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// isLimitedOffer reports whether a shop item is sold as a limited-time offer
// (masterdata.LimitedOffers). Unlike the other packs, these keep their stock:
// one purchase each, while open.
func isLimitedOffer(shopItemId int32) bool {
	offers, _ := masterdata.LimitedOffers()
	for _, o := range offers {
		if o.ShopItemId == shopItemId {
			return true
		}
	}
	return false
}

// checkLimitedOffer refuses a limited offer that is closed or already bought up.
func checkLimitedOffer(catalog *masterdata.ShopCatalog, user *store.UserState, item masterdata.EntityMShopItem, limited bool, now int64) error {
	if !limited {
		return nil
	}
	offers, _ := masterdata.LimitedOffers()
	open := false
	for _, o := range offers {
		if o.ShopItemId == item.ShopItemId && o.OpenDatetime <= now && now < o.CloseDatetime {
			open = true
		}
	}
	if !open {
		return fmt.Errorf("limited offer %d is not open", item.ShopItemId)
	}
	if max, ok := catalog.LimitedStock[item.ShopItemLimitedStockId]; ok && user.ShopItems[item.ShopItemId].BoughtCount >= max {
		return fmt.Errorf("limited offer %d already bought", item.ShopItemId)
	}
	return nil
}
