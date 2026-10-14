package masterdata

import (
	"log"
	"sync"

	"lunar-tear/server/internal/utils"
)

// Limited-time offers. The Limited shop (m_config LIMITED_SHOP_ID) sells
// packs that only show while the player has them "opened" (IUserLimitedOpen,
// target type SHOP_ITEM_CELL with the cell's id). What opened each one for a
// player is not in the game data, so each opens for its original sale period:
// the cell's term (m_shop_item_cell_term), or the shop's own dates when it
// has none. With the Original calendar those dates are the loop's; with
// everything open the patched game data keeps them open.

// LimitedOffer is one limited-open shop cell and when it is open.
type LimitedOffer struct {
	ShopId, ShopItemCellId, ShopItemId int32
	OpenDatetime, CloseDatetime        int64
}

// LimitedOffers are the limited-time offers and their shops' windows.
var LimitedOffers = sync.OnceValues(func() ([]LimitedOffer, map[int32]LimitedOffer) {
	read := func(err error, name string) {
		if err != nil {
			log.Printf("[LimitedOpen] %s: %v", name, err)
		}
	}
	opens, err := utils.ReadTable[EntityMShopItemCellLimitedOpen]("m_shop_item_cell_limited_open")
	read(err, "m_shop_item_cell_limited_open")
	cells, err := utils.ReadTable[EntityMShopItemCell]("m_shop_item_cell")
	read(err, "m_shop_item_cell")
	groups, err := utils.ReadTable[EntityMShopItemCellGroup]("m_shop_item_cell_group")
	read(err, "m_shop_item_cell_group")
	terms, err := utils.ReadTable[EntityMShopItemCellTerm]("m_shop_item_cell_term")
	read(err, "m_shop_item_cell_term")
	shops, err := utils.ReadTable[EntityMShop]("m_shop")
	read(err, "m_shop")

	itemOfCell := map[int32]int32{}
	for _, c := range cells {
		itemOfCell[c.ShopItemCellId] = c.ShopItemId
	}
	termById := map[int32]EntityMShopItemCellTerm{}
	for _, t := range terms {
		termById[t.ShopItemCellTermId] = t
	}
	shopOfGroup := map[int32]EntityMShop{}
	for _, s := range shops {
		shopOfGroup[s.ShopItemCellGroupId] = s
	}
	type place struct {
		shop EntityMShop
		term int32
	}
	where := map[int32]place{}
	for _, g := range groups {
		if s, ok := shopOfGroup[g.ShopItemCellGroupId]; ok {
			where[g.ShopItemCellId] = place{s, g.ShopItemCellTermId}
		}
	}
	var offers []LimitedOffer
	shopWindows := map[int32]LimitedOffer{}
	for _, o := range opens {
		p, ok := where[o.ShopItemCellId]
		if !ok {
			continue
		}
		open, close := p.shop.StartDatetime, p.shop.EndDatetime
		if t, ok := termById[p.term]; ok && p.term != 0 {
			open, close = t.StartDatetime, t.EndDatetime
		}
		offers = append(offers, LimitedOffer{ShopId: p.shop.ShopId, ShopItemCellId: o.ShopItemCellId, ShopItemId: itemOfCell[o.ShopItemCellId],
			OpenDatetime: open, CloseDatetime: close})
		shopWindows[p.shop.ShopId] = LimitedOffer{ShopId: p.shop.ShopId, OpenDatetime: p.shop.StartDatetime, CloseDatetime: p.shop.EndDatetime}
	}
	return offers, shopWindows
})
