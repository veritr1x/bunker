package service

import (
	"sort"
	"sync"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// The item shop (shop 2001) sells its 17 items for gold, each with a daily
// stock. Restocking it early costs gems that rise with each refresh of the
// day (m_shop_replaceable_gem: 10, 30, 50 ... 500). LineupUpdateCount is the
// number of the next refresh, from 1: the game prices the refresh from it
// (and fails on 0), and it goes back to 1 at the daily reset.

var replaceableGems = sync.OnceValue(func() []masterdata.EntityMShopReplaceableGem {
	rows := table[masterdata.EntityMShopReplaceableGem]("m_shop_replaceable_gem")
	sort.Slice(rows, func(i, j int) bool { return rows[i].LineupUpdateCountLowerLimit < rows[j].LineupUpdateCountLowerLimit })
	return rows
})

// replaceableRefreshGems is the price of refresh number count, as the game shows it.
func replaceableRefreshGems(count int32) int32 {
	price := int32(0)
	for _, r := range replaceableGems() {
		if r.LineupUpdateCountLowerLimit <= count {
			price = r.NecessaryGem
		}
	}
	return price
}

// syncLineupUpdateCount starts the day's refresh count at 1.
func syncLineupUpdateCount(user *store.UserState, now int64) {
	r := &user.ShopReplaceable
	if r.LineupUpdateCount < 1 || r.LatestLineupUpdateDatetime < gametime.StartOfDay(now) {
		if r.LineupUpdateCount != 1 {
			r.LineupUpdateCount = 1
			r.LatestVersion = now
		}
	}
}
