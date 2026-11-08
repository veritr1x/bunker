package service

import (
	"fmt"
	"log"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// OpenLimitedOffers opens, with the Original calendar, each limited-time
// offer whose trigger the player has met (masterdata.LimitedTriggers) during
// its sale period, for its hours: a completion pack from now, when its
// chapter is found cleared (a player who had cleared it before gets it at
// their next login, as the notices said); a Jumpstart pack from when the
// loadout tutorial ended. An offer opens once. With everything open nothing
// is recorded: every offer stays open (userdata's IUserLimitedOpen).
func OpenLimitedOffers(u *store.UserState, now int64) {
	if gametime.CurrentCalendar() == nil {
		return
	}
	offers, _ := masterdata.LimitedOffers()
	for _, o := range offers {
		if _, done := u.Ext.LimitedOpens[o.ShopItemCellId]; done {
			continue
		}
		tr, ok := masterdata.LimitedTriggers[o.ShopItemCellId]
		if !ok {
			continue
		}
		at, ok := limitedTriggerTime(u, tr, now)
		if !ok || at < o.OpenDatetime || at >= o.CloseDatetime {
			continue
		}
		if original := at - gametime.CalendarOffset(); (tr.Before != 0 && original >= tr.Before) || (tr.From != 0 && original < tr.From) {
			continue
		}
		if u.Ext.LimitedOpens == nil {
			u.Ext.LimitedOpens = map[int32]store.LimitedOpenState{}
		}
		u.Ext.LimitedOpens[o.ShopItemCellId] = store.LimitedOpenState{Open: at, Close: at + tr.Hours*3_600_000}
		log.Printf("[LimitedOpen] user %d: cell %d open for %d hours", u.UserId, o.ShopItemCellId, tr.Hours)
	}
}

// limitedTriggerTime is when an offer's trigger happened for the player, if it has.
func limitedTriggerTime(u *store.UserState, tr masterdata.LimitedTrigger, now int64) (int64, bool) {
	switch tr.Kind {
	case masterdata.TriggerChapter:
		quests := masterdata.ChapterQuests()[[2]int32{tr.Chapter, tr.Difficulty}]
		if len(quests) == 0 {
			return 0, false
		}
		for _, q := range quests {
			if u.Quests[q].ClearCount == 0 {
				return 0, false
			}
		}
		return now, true
	case masterdata.TriggerQuest:
		return now, u.Quests[tr.Quest].ClearCount > 0
	case masterdata.TriggerLoadout, masterdata.TriggerNewcomer:
		t := u.Tutorials[masterdata.LoadoutTutorial]
		if t.ProgressPhase < masterdata.LoadoutTutorialDone || t.LatestVersion == 0 {
			return 0, false
		}
		return t.LatestVersion, true
	}
	return 0, false
}

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
	calendar := gametime.CurrentCalendar() != nil
	for _, o := range offers {
		if o.ShopItemId != item.ShopItemId {
			continue
		}
		window := store.LimitedOpenState{Open: o.OpenDatetime, Close: o.CloseDatetime}
		if calendar { // the player's own window (OpenLimitedOffers)
			window = user.Ext.LimitedOpens[o.ShopItemCellId]
		}
		if window.Open <= now && now < window.Close {
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
