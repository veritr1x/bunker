package gacha

import (
	"fmt"
	"math/rand"
	"time"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/store"
)

// Box summons (chapter summons): each box holds a fixed set of items
// (GachaCatalogEntry.BoxContents) drawn without putting them back. The box
// refills on the first of every month, and can be reset early once its target
// items have all been drawn or it is empty (see masterdata.chapterBox).

// monthStart is the start of the game month containing now.
func monthStart(now int64) int64 {
	t := time.UnixMilli(now).In(gametime.Zone)
	return time.Date(t.Year(), t.Month(), 1, 0, 0, 0, 0, gametime.Zone).UnixMilli()
}

// BoxState is a box summon's box for the player at now, refilled first if a
// new month began: the items left, and whether every target was drawn.
type BoxState struct {
	Left, Drawn  int32
	TargetsDrawn bool
}

// refillBox empties the drawn counts of bs when a new month began.
func refillBox(user *store.UserState, entry store.GachaCatalogEntry, bs *store.GachaBannerState, now int64) {
	month := monthStart(now)
	if user.Ext.BoxMonth == nil {
		user.Ext.BoxMonth = map[int32]int64{}
	}
	if user.Ext.BoxMonth[entry.GachaId] < month {
		bs.BoxDrewCounts = map[int32]int32{}
		user.Ext.BoxMonth[entry.GachaId] = month
	}
}

// Box reports the player's box of entry (without refilling it).
func Box(user *store.UserState, entry store.GachaCatalogEntry, now int64) BoxState {
	bs := user.Gacha.BannerStates[entry.GachaId]
	fresh := user.Ext.BoxMonth[entry.GachaId] < monthStart(now)
	st := BoxState{TargetsDrawn: true}
	for _, c := range entry.BoxContents {
		drew := bs.BoxDrewCounts[c.PossessionId]
		if fresh {
			drew = 0
		}
		st.Left += c.Count - drew
		st.Drawn += drew
		if c.IsTarget && drew < c.Count {
			st.TargetsDrawn = false
		}
	}
	return st
}

// checkBoxDraw refuses a draw of count items when fewer are left.
func checkBoxDraw(user *store.UserState, entry store.GachaCatalogEntry, count int, now int64) error {
	if len(entry.BoxContents) == 0 {
		return nil
	}
	if left := Box(user, entry, now).Left; int32(count) > left {
		return fmt.Errorf("gacha %d: %d left in the box, %d asked", entry.GachaId, left, count)
	}
	return nil
}

// drawFixedBox draws count items from the player's box of entry.
func drawFixedBox(user *store.UserState, entry store.GachaCatalogEntry, bs *store.GachaBannerState, count int, now int64) []DrawnItem {
	refillBox(user, entry, bs, now)
	if bs.BoxDrewCounts == nil {
		bs.BoxDrewCounts = map[int32]int32{}
	}
	var left []int // index into BoxContents, once per item left
	for i, c := range entry.BoxContents {
		for range c.Count - bs.BoxDrewCounts[c.PossessionId] {
			left = append(left, i)
		}
	}
	out := make([]DrawnItem, 0, count)
	for range count {
		if len(left) == 0 {
			break
		}
		pick := rand.Intn(len(left))
		c := entry.BoxContents[left[pick]]
		left = append(left[:pick], left[pick+1:]...)
		bs.BoxDrewCounts[c.PossessionId]++
		out = append(out, DrawnItem{PossessionType: c.PossessionType, PossessionId: c.PossessionId, RarityType: c.RarityType})
	}
	return out
}

// canResetBox: once every target was drawn, or the box is empty.
func canResetBox(user *store.UserState, entry store.GachaCatalogEntry, now int64) bool {
	st := Box(user, entry, now)
	return st.Left == 0 || st.TargetsDrawn
}
