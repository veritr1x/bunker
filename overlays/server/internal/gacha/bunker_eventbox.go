package gacha

import (
	"fmt"
	"math/rand"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// Event summons (masterdata.EventSummon): a box per level. The player's level
// is the banner state's BoxNumber (1 at first) and what they drew from it is
// BoxDrewCounts by prize index; both live on the event's own summon id.

// EventLevel is the level the player is on.
func EventLevel(bs store.GachaBannerState) int32 {
	return max(bs.BoxNumber, 1)
}

func eventLevel(bs store.GachaBannerState, box masterdata.EventSummon) masterdata.EventLevel {
	return box.Levels[min(int(EventLevel(bs)), len(box.Levels))-1]
}

// EventPrizeLeft is how many of a level prize are left.
func EventPrizeLeft(bs store.GachaBannerState, index int, p masterdata.BoxPrize) int32 {
	return max(p.Stock-bs.BoxDrewCounts[int32(index)], 0)
}

// drawEventBox draws count prizes from the player's current level: one of
// the level's prizes with its Chance (every one left alike), else one from
// the unlimited pool.
func drawEventBox(bs *store.GachaBannerState, box masterdata.EventSummon, unlimited []masterdata.BoxPrize, count int) []DrawnItem {
	if bs.BoxDrewCounts == nil {
		bs.BoxDrewCounts = map[int32]int32{}
	}
	level := eventLevel(*bs, box)
	out := make([]DrawnItem, 0, count)
	for range count {
		left := int32(0)
		for i, p := range level.Items {
			left += EventPrizeLeft(*bs, i, p)
		}
		var p masterdata.BoxPrize
		switch {
		case left > 0 && rand.Float64() < level.Chance:
			roll := rand.Int31n(left)
			for i, q := range level.Items {
				n := EventPrizeLeft(*bs, i, q)
				if roll < n {
					p = q
					bs.BoxDrewCounts[int32(i)]++
					break
				}
				roll -= n
			}
		case len(unlimited) > 0:
			p = unlimited[rand.Intn(len(unlimited))]
		default:
			continue
		}
		out = append(out, DrawnItem{PossessionType: p.Type, PossessionId: p.Id, Count: max(p.Count, 1)})
	}
	return out
}

// eventTargetsDrawn: every target of the current level is drawn.
func eventTargetsDrawn(bs store.GachaBannerState, box masterdata.EventSummon) bool {
	for i, p := range eventLevel(bs, box).Items {
		if p.Target && EventPrizeLeft(bs, i, p) > 0 {
			return false
		}
	}
	return true
}

// eventLevelEmpty: nothing is left of the current level's prizes.
func eventLevelEmpty(bs store.GachaBannerState, box masterdata.EventSummon) bool {
	for i, p := range eventLevel(bs, box).Items {
		if EventPrizeLeft(bs, i, p) > 0 {
			return false
		}
	}
	return true
}

// EventCanAdvance is the Level Up (or, on the last level, Prize
// Replenishment) button: targets drawn, or the last level emptied.
func EventCanAdvance(bs store.GachaBannerState, box masterdata.EventSummon) bool {
	if int(EventLevel(bs)) >= len(box.Levels) {
		return eventLevelEmpty(bs, box)
	}
	return eventTargetsDrawn(bs, box)
}

// resetEventBox levels the player up, or replenishes the last level.
func resetEventBox(user *store.UserState, box masterdata.EventSummon) error {
	bs := user.Gacha.BannerStates[box.Base]
	if !EventCanAdvance(bs, box) {
		return fmt.Errorf("gacha %d: level %d is not done", box.Base, EventLevel(bs))
	}
	bs.GachaId = box.Base
	bs.BoxNumber = min(EventLevel(bs)+1, int32(len(box.Levels)))
	bs.BoxDrewCounts = map[int32]int32{}
	user.Gacha.BannerStates[box.Base] = bs
	return nil
}
