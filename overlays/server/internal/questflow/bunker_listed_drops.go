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

// A memory dungeon's higher rarities: 1 in 10 one step up, then 3 times rarer
// for each further step (1 in 30, 1 in 90). An estimate: a 4★ set is a long farm.
const (
	listedUpgradeOneIn int64 = 10
	listedUpgradeStep  int64 = 3
)

var listedDropCatalog = masterdata.ListedDrops

// listedDropsFor is listedDrops for a quest or an earlier run's copy of it.
func listedDropsFor(questId int32, shown, granted []RewardGrant, rate func(int32) int32, roll func(int64) int64, boost dropBoost) []RewardGrant {
	return listedDrops(listedDropCatalog(), store.OriginalQuest(questId), shown, granted, rate, roll, boost)
}

// listedDrops rolls, for quest questId (an original id):
//   - each material the quest's route lists that is neither shown nor granted
//     already, by its rarity;
//   - for each rarity R at which shown has a piece of a memoir set, each piece
//     of that set not shown at R, at R.
//
// shown is the clear's pickup drops, granted everything granted so far.
// rate applies the quest's drop-rate campaign; roll(n) is in [0, n); boost
// raises each roll's chance (bunker_drop_boost.go).
func listedDrops(c masterdata.ListedDropCatalog, questId int32, shown, granted []RewardGrant, rate func(int32) int32, roll func(int64) int64, boost dropBoost) []RewardGrant {
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
		if !boostedHit(odds.OneIn, boost.of(model.PossessionTypeMaterial, m.MaterialId), roll) {
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
	// The quest's chapter screens show memoirs too: their sets complete here.
	// A screen piece is rolled like any missing one unless the chapter
	// memoirs granted it this clear (grantedKinds).
	screenKinds := map[masterdata.PartsKind]bool{}
	for _, id := range c.ChapterShown[questId] {
		if k, ok := c.Parts[id]; ok {
			screenKinds[k] = true
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
	setKinds := map[masterdata.PartsKind]bool{}
	for k := range shownKinds {
		setKinds[k] = true
	}
	for k := range screenKinds {
		setKinds[k] = true
	}
	for k := range setKinds {
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
			if boostedHit(listedMemoirOneIn, boost.of(model.PossessionTypeParts, id), roll) {
				out = append(out, RewardGrant{PossessionType: model.PossessionTypeParts, PossessionId: id, Count: rate(1)})
			}
		}
	}

	// A memory dungeon also drops each set its drops show at the rarities above
	// the highest they show it at: ever rarer for each step up.
	if !c.Dungeon[questId] {
		return out
	}
	// Stepping up from the quest's own drops: a chapter screen may show a
	// higher rarity, whose pieces are skipped as shown, not the ones between.
	top := map[int32]int32{}
	for _, g := range shown {
		if g.PossessionType != model.PossessionTypeParts {
			continue
		}
		if k, ok := c.Parts[g.PossessionId]; ok && len(c.SetOf[k.Group]) > 0 {
			first := c.SetOf[k.Group][0]
			top[first] = max(top[first], k.Rarity)
		}
	}
	firsts := make([]int32, 0, len(top))
	for first := range top {
		firsts = append(firsts, first)
	}
	sort.Slice(firsts, func(i, j int) bool { return firsts[i] < firsts[j] })
	for _, first := range firsts {
		oneIn := listedUpgradeOneIn
		for rarity := top[first] + 10; rarity <= 40; rarity += 10 {
			if seen[setAt{first, rarity}] { // the set completion rolled this rarity already
				oneIn *= listedUpgradeStep
				continue
			}
			for _, g := range c.SetOf[first] {
				k := masterdata.PartsKind{Group: g, Rarity: rarity}
				id, ok := c.PartsFor[k]
				if shownKinds[k] || grantedKinds[k] || !ok {
					continue
				}
				if boostedHit(oneIn, boost.of(model.PossessionTypeParts, id), roll) {
					out = append(out, RewardGrant{PossessionType: model.PossessionTypeParts, PossessionId: id, Count: rate(1)})
				}
			}
			oneIn *= listedUpgradeStep
		}
	}
	return out
}
