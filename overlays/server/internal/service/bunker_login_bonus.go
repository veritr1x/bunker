package service

import (
	"log"
	"sort"
	"sync"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// Dated login bonuses. Besides the everyday stamp card (login bonus 1, kept
// in UserState.LoginBonus), the game data has over a hundred dated cards for
// events and anniversaries (m_login_bonus with start and end dates). Each one
// open today gets one stamp per game day until its card is full; its reward
// goes to the gift box like the everyday one. The five that wait for a start
// condition (m_login_bonus LoginBonusStartConditionId) stay off: the
// condition table is not in the game data.
//
// Only with the Original calendar: with everything open, the patched game
// data keeps every card open forever, which would stamp all of them each day.

var loginBonuses = sync.OnceValue(func() []masterdata.EntityMLoginBonus {
	rows := table[masterdata.EntityMLoginBonus]("m_login_bonus")
	sort.Slice(rows, func(i, j int) bool { return rows[i].LoginBonusId < rows[j].LoginBonusId })
	return rows
})

// openEventLoginBonuses are the dated cards that take a stamp at now.
func openEventLoginBonuses(u *store.UserState, now int64) []masterdata.EntityMLoginBonus {
	if gametime.CurrentCalendar() == nil {
		return nil
	}
	var out []masterdata.EntityMLoginBonus
	for _, b := range loginBonuses() {
		end := min(b.EndDatetime, b.StampReceiveEndDatetime)
		everyday := b.LoginBonusId == u.LoginBonus.LoginBonusId || b.EndDatetime >= neverEnds
		if everyday || b.LoginBonusStartConditionId != 0 || now < b.StartDatetime || now >= end {
			continue
		}
		out = append(out, b)
	}
	return out
}

// stampEventLoginBonuses stamps each open dated card once for the game day.
func stampEventLoginBonuses(catalog *masterdata.LoginBonusCatalog, u *store.UserState, now int64) {
	today := gametime.StartOfDay(now)
	for _, b := range openEventLoginBonuses(u, now) {
		st, ok := u.Ext.EventLoginBonuses[b.LoginBonusId]
		if !ok {
			st = store.UserLoginBonusState{LoginBonusId: b.LoginBonusId, CurrentPageNumber: 1}
		}
		if st.LatestRewardReceiveDatetime >= today {
			continue
		}
		page, stamp, reward, err := resolveNextStamp(catalog, st)
		if err != nil {
			continue // card full
		}
		addLoginBonusGift(u, reward, now)
		st.CurrentPageNumber, st.CurrentStampNumber = page, stamp
		st.LatestRewardReceiveDatetime, st.LatestVersion = now, now
		if u.Ext.EventLoginBonuses == nil {
			u.Ext.EventLoginBonuses = map[int32]store.UserLoginBonusState{}
		}
		u.Ext.EventLoginBonuses[b.LoginBonusId] = st
		log.Printf("[LoginBonusService] event bonus %d stamp %d: possType=%d possId=%d count=%d (-> gift box)",
			b.LoginBonusId, stamp, reward.PossessionType, reward.PossessionId, reward.Count)
	}
}
