package questflow

import (
	"sort"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Listed drops (masterdata/bunker_listed_drops.go): what a clear adds from
// what the game lists for the quest but its screen doesn't show. The live
// game's rates were never published; these are estimates. Displayed drops
// still drop on every clear (Zenith's Brilliance on every Dark Memory run),
// so even the rarest listed material at 1 in 10 stays below the live game's
// ratio to it (nierrein.guide: Polycrystal half as often as Zenith).

type listedOdds struct {
	OneIn    int64
	Min, Max int32
}

// By the material's rarity; a rarity not here does not drop.
var listedMaterialOdds = map[int32]listedOdds{
	10: {2, 1, 2},
	20: {3, 1, 1},
	30: {5, 1, 1},
	40: {10, 1, 1},
}

// Each missing piece of a set the quest shows: a set takes a few runs.
const listedMemoirOneIn = 3

var listedDropCatalog = masterdata.ListedDrops

// listedDropsFor is listedDrops for a quest or an earlier run's copy of it.
func listedDropsFor(questId int32, shown, granted []RewardGrant, rate func(int32) int32, roll func(int64) int64) []RewardGrant {
	return listedDrops(listedDropCatalog(), store.OriginalQuest(questId), shown, granted, rate, roll)
}

// listedDrops rolls, for quest questId (an original id):
//   - each material the quest's route lists that is neither shown nor granted
//     already, by its rarity;
//   - for each rarity R at which shown has a piece of a memoir set, each piece
//     of that set not shown at R, at R.
//
// shown is the clear's pickup drops, granted everything granted so far.
// rate applies the quest's drop-rate campaign; roll(n) is in [0, n).
func listedDrops(c masterdata.ListedDropCatalog, questId int32, shown, granted []RewardGrant, rate func(int32) int32, roll func(int64) int64) []RewardGrant {
	type item struct {
		t  model.PossessionType
		id int32
	}
	have := map[item]bool{}
	for _, list := range [][]RewardGrant{shown, granted} {
		for _, g := range list {
			have[item{g.PossessionType, g.PossessionId}] = true
		}
	}

	var out []RewardGrant
	for _, m := range c.Materials[questId] {
		odds, ok := listedMaterialOdds[m.Rarity]
		if !ok || have[item{model.PossessionTypeMaterial, m.MaterialId}] {
			continue
		}
		if roll(odds.OneIn) != 0 {
			continue
		}
		count := odds.Min
		if odds.Max > odds.Min {
			count += int32(roll(int64(odds.Max - odds.Min + 1)))
		}
		out = append(out, RewardGrant{PossessionType: model.PossessionTypeMaterial, PossessionId: m.MaterialId, Count: rate(count)})
	}

	shownKinds := map[masterdata.PartsKind]bool{}
	for _, g := range shown {
		if g.PossessionType != model.PossessionTypeParts {
			continue
		}
		if k, ok := c.Parts[g.PossessionId]; ok {
			shownKinds[k] = true
		}
	}
	// The quest's chapter screens show memoirs too; the chapter memoirs grant
	// those pieces, and their sets complete here.
	for _, id := range c.ChapterShown[questId] {
		if k, ok := c.Parts[id]; ok {
			shownKinds[k] = true
		}
	}
	// A piece another rule granted already (the chapter memoirs) isn't rolled again.
	grantedKinds := map[masterdata.PartsKind]bool{}
	for _, g := range granted {
		if g.PossessionType != model.PossessionTypeParts {
			continue
		}
		if k, ok := c.Parts[g.PossessionId]; ok {
			grantedKinds[k] = true
		}
	}
	type setAt struct{ first, rarity int32 }
	seen := map[setAt]bool{}
	var sets []setAt
	for k := range shownKinds {
		set := c.SetOf[k.Group]
		if len(set) == 0 {
			continue
		}
		s := setAt{set[0], k.Rarity}
		if !seen[s] {
			seen[s] = true
			sets = append(sets, s)
		}
	}
	sort.Slice(sets, func(i, j int) bool {
		return sets[i].first < sets[j].first || sets[i].first == sets[j].first && sets[i].rarity < sets[j].rarity
	})
	for _, s := range sets {
		for _, g := range c.SetOf[s.first] {
			k := masterdata.PartsKind{Group: g, Rarity: s.rarity}
			id, ok := c.PartsFor[k]
			if shownKinds[k] || grantedKinds[k] || !ok {
				continue
			}
			if roll(listedMemoirOneIn) == 0 {
				out = append(out, RewardGrant{PossessionType: model.PossessionTypeParts, PossessionId: id, Count: rate(1)})
			}
		}
	}
	return out
}
