package missions

import (
	"strings"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// The profile's play history (GetUserProfile GamePlayHistory.historyItem):
// the game's counters, named by profile.history.name.NNN where NNN is the
// historyItemId. GetUserGamePlayNote asks for one of them by the same id; the
// smartphone's pedometer asks for HistoryWalkDistance (SmartphoneTopPresenter.
// GetServerWalkDistanceAsync sends 13) and adds the distance not yet sent.
const (
	HistoryChapterSummons     = 1  // Chapter Summons Performed
	HistoryEventSummons       = 2  // Event Summons Performed
	HistoryItemShopPurchases  = 3  // Purchases Made at the Item Shop
	HistoryExchangeTrades     = 4  // Trades Made at the Exchange
	HistoryPartyEliminated    = 5  // Party Eliminated
	HistoryExploreGroup1      = 6  // Shooting Games Played; 7-9 Exploration 2-4 (explore groups 2-4)
	HistoryPictureBooks       = 10 // Picturebooks Watched: not known to the server
	HistoryBestWinStreak      = 11 // Best Arena Win Streak
	HistoryMissionsCompleted  = 12 // Missions Completed
	HistoryWalkDistance       = 13 // Distance Walked in Cage (m)
	HistoryCostumeTypes       = 14 // Character Types Collected
	HistoryWeaponTypes        = 15 // Weapon Types Collected
	HistoryCompanionTypes     = 16 // Companion Types Collected
	HistoryPartsTypes         = 17 // Memoir Types Collected
	HistoryDaysLoggedIn       = 18 // Days Logged In
	HistoryArenaMatches       = 19 // Arena Matches Played
	HistoryCostumeEnhance     = 20 // Times Characters Enhanced
	HistoryCostumeSkill       = 21 // Times Character Skills Enhanced
	HistoryCostumeLimitBreak  = 22 // Times Characters Ascended
	HistoryWeaponEnhance      = 23 // Times Weapons Enhanced
	HistoryWeaponSkill        = 24 // Times Weapon Skills Enhanced
	HistoryWeaponEvolve       = 25 // Times Weapons Evolved
	HistoryWeaponLimitBreak   = 26 // Times Weapons Ascended
	HistoryCompanionEnhance   = 27 // Times Companions Enhanced
	HistoryPartsEnhance       = 28 // Times Memoirs Enhanced
	HistoryBlackBirds         = 29 // Black Birds Slain: not known to the server
	historyCount              = 29
	shopGroupItemShop         = 3 // ShopGroupType ITEM_SHOP
	shopGroupExchange         = 4 // ShopGroupType EXCHANGE_SHOP
	historyExploreGroupsShown = 4
)

// historyKinds are counters that count what a mission kind counts, every
// request alike.
var historyKinds = map[int32]string{
	HistoryPartyEliminated: "battle_annihilated", HistoryWalkDistance: "cage_walk", HistoryArenaMatches: "pvp_play",
	HistoryCostumeEnhance: "costume_enhance", HistoryWeaponEnhance: "weapon_enhance",
	HistoryCompanionEnhance: "companion_enhance", HistoryPartsEnhance: "parts_enhance",
}

// historyMethods are counters of requests: one each.
var historyMethods = map[string]int32{
	"/apb.api.costume.CostumeService/EnhanceActiveSkill": HistoryCostumeSkill,
	"/apb.api.costume.CostumeService/LimitBreak":         HistoryCostumeLimitBreak,
	"/apb.api.weapon.WeaponService/EnhanceSkill":         HistoryWeaponSkill,
	"/apb.api.weapon.WeaponService/Evolve":               HistoryWeaponEvolve,
	"/apb.api.weapon.WeaponService/LimitBreakByWeapon":   HistoryWeaponLimitBreak,
	"/apb.api.weapon.WeaponService/LimitBreakByMaterial": HistoryWeaponLimitBreak,
}

// recordHistory counts what a request adds to the play history. A save that
// had no history yet starts from what its missions already counted.
func (cat *Catalog) recordHistory(before, after *store.UserState, c *counts, method string, req any, start bool) {
	h := after.Ext.History
	if start {
		// The missions have counted this request already.
		cat.startHistory(after)
		return
	}
	for id, kind := range historyKinds {
		h[id] += c.amount[kind]
	}
	for id, n := range c.explores {
		if g := cat.exploreGroups[id]; g > 0 && g <= historyExploreGroupsShown {
			h[HistoryExploreGroup1+g-1] += n
		}
	}
	if id, ok := historyMethods[method]; ok {
		h[id]++
	}
	if r, ok := req.(*pb.BuyRequest); ok && strings.HasSuffix(method, "ShopService/Buy") {
		switch cat.shopGroups[r.ShopId] {
		case shopGroupItemShop:
			h[HistoryItemShopPurchases]++
		case shopGroupExchange:
			h[HistoryExchangeTrades]++
		}
	}
	h[HistoryBestWinStreak] = max(h[HistoryBestWinStreak], int64(after.Ext.Pvp.WinStreak))
	for id, m := range after.Missions {
		old := before.Missions[id]
		if m.MissionProgressStatusType >= StatusClear && m.ClearDatetime != 0 && m.ClearDatetime != old.ClearDatetime {
			h[HistoryMissionsCompleted]++
		}
	}
	dropZeros(h)
}

func dropZeros(h map[int32]int64) {
	for id, n := range h {
		if n == 0 {
			delete(h, id)
		}
	}
}

// startHistory fills the counters from the save: missions done, and the best
// progress of the missions that count the same thing (a lower bound).
func (cat *Catalog) startHistory(u *store.UserState) {
	h := u.Ext.History
	best := func(ok func(m *Mission) bool) int64 {
		var n int64
		for _, m := range cat.Missions {
			if !m.Daily() && ok(m) {
				n = max(n, int64(u.Missions[m.MissionId].ProgressValue))
			}
		}
		return n
	}
	for id, kind := range historyKinds {
		h[id] = max(h[id], best(func(m *Mission) bool { return m.Rule.Kind == kind }))
	}
	h[HistoryArenaMatches] = max(h[HistoryArenaMatches], int64(u.Ext.Pvp.Season.AttackWins+u.Ext.Pvp.Season.AttackLosses))
	h[HistoryBestWinStreak] = max(h[HistoryBestWinStreak], best(func(m *Mission) bool { return m.Rule.Kind == "pvp_streak" }))
	for g := int32(1); g <= historyExploreGroupsShown; g++ {
		var explores []int32
		for id, group := range cat.exploreGroups {
			if group == g {
				explores = append(explores, id)
			}
		}
		if len(explores) == 0 {
			continue
		}
		h[HistoryExploreGroup1+g-1] = max(h[HistoryExploreGroup1+g-1], best(func(m *Mission) bool {
			if m.Rule.Kind != "explore_finish" || len(m.Rule.Explores) == 0 {
				return false
			}
			for _, id := range m.Rule.Explores {
				if !contains(explores, id) {
					return false
				}
			}
			return true
		}))
	}
	var done int64
	for _, m := range u.Missions {
		if m.MissionProgressStatusType >= StatusClear {
			done++
		}
	}
	h[HistoryMissionsCompleted] = max(h[HistoryMissionsCompleted], done)
	dropZeros(h)
}

// PlayHistory is the profile's play history, every counter in order.
func (cat *Catalog) PlayHistory(u *store.UserState) []*pb.PlayHistoryItem {
	out := make([]*pb.PlayHistoryItem, 0, historyCount)
	for id := int32(1); id <= historyCount; id++ {
		out = append(out, &pb.PlayHistoryItem{HistoryItemId: id, Count: cat.HistoryValue(u, id)})
	}
	return out
}

// HistoryValue is one play history counter.
func (cat *Catalog) HistoryValue(u *store.UserState, id int32) int64 {
	switch id {
	case HistoryChapterSummons, HistoryEventSummons:
		want := model.GachaLabelChapter
		if id == HistoryEventSummons {
			want = model.GachaLabelEvent
		}
		var n int64
		for gachaId, b := range u.Gacha.BannerStates {
			if GachaLabel != nil && GachaLabel(gachaId) == want {
				n += int64(b.DrawCount)
			}
		}
		return n
	case HistoryBestWinStreak:
		return max(u.Ext.History[id], int64(u.Ext.Pvp.WinStreak))
	case HistoryCostumeTypes, HistoryWeaponTypes, HistoryCompanionTypes, HistoryPartsTypes:
		e := cat.encyclopedia
		seen := map[int32]bool{}
		switch id {
		case HistoryCostumeTypes:
			for _, co := range u.Costumes {
				seen[co.CostumeId] = e.costumes[co.CostumeId]
			}
		case HistoryWeaponTypes:
			for w := range u.WeaponNotes {
				seen[w] = e.weapons[w]
			}
			for _, w := range u.Weapons {
				seen[w.WeaponId] = e.weapons[w.WeaponId]
			}
		case HistoryCompanionTypes:
			for _, co := range u.Companions {
				seen[co.CompanionId] = e.companions[co.CompanionId]
			}
		case HistoryPartsTypes:
			for g := range u.PartsGroupNotes {
				seen[g] = e.partsGroups[g]
			}
		}
		var n int64
		for _, listed := range seen {
			if listed {
				n++
			}
		}
		return n
	case HistoryDaysLoggedIn:
		return int64(u.Login.TotalLoginCount)
	}
	return u.Ext.History[id]
}
