package masterdata

import (
	"log"
	"sort"

	"lunar-tear/server/internal/bunkercache"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/utils"
)

// Listed drops: what the game says a quest drops beyond what its screen
// shows. The live game's enemies dropped these at random, from server tables
// that never shipped. Two kinds are known from the client's data:
//   - materials whose "where to get" list (m_possession_acquisition_route,
//     route type 1) names the quest;
//   - the other pieces of a memoir set the quest shows a piece of.
// questflow/bunker_listed_drops.go rolls them.

const acquisitionRouteQuest = 1

// PartsKind is a memoir piece at one rarity; its five ranks share it.
type PartsKind struct{ Group, Rarity int32 }

// ListedMaterial is a material a quest's route lists, with its rarity (0 when
// the material is unknown).
type ListedMaterial struct{ MaterialId, Rarity int32 }

type ListedDropCatalog struct {
	Materials map[int32][]ListedMaterial // original quest id -> route-listed materials, in route order
	Parts     map[int32]PartsKind        // parts id -> kind
	SetOf     map[int32][]int32          // parts group -> its set's three groups, ascending
	PartsFor  map[PartsKind]int32        // kind -> the lowest parts id of that group and rarity
}

var ListedDrops = bunkercache.Value(func() ListedDropCatalog {
	var t listedDropTables
	var err error
	read := func(name string) {
		if err != nil {
			log.Printf("[ListedDrops] %s: %v", name, err)
		}
	}
	t.routes, err = utils.ReadTable[EntityMPossessionAcquisitionRoute]("m_possession_acquisition_route")
	read("m_possession_acquisition_route")
	t.materials, err = utils.ReadTable[EntityMMaterial]("m_material")
	read("m_material")
	t.parts, err = utils.ReadTable[EntityMParts]("m_parts")
	read("m_parts")
	t.partsGroups, err = utils.ReadTable[EntityMPartsGroup]("m_parts_group")
	read("m_parts_group")
	return listedDropCatalog(t)
})

type listedDropTables struct {
	routes      []EntityMPossessionAcquisitionRoute
	materials   []EntityMMaterial
	parts       []EntityMParts
	partsGroups []EntityMPartsGroup
}

func listedDropCatalog(t listedDropTables) ListedDropCatalog {
	c := ListedDropCatalog{
		Materials: map[int32][]ListedMaterial{},
		Parts:     map[int32]PartsKind{},
		SetOf:     map[int32][]int32{},
		PartsFor:  map[PartsKind]int32{},
	}

	rarity := map[int32]int32{}
	for _, m := range t.materials {
		rarity[m.MaterialId] = m.RarityType
	}
	routes := append([]EntityMPossessionAcquisitionRoute(nil), t.routes...)
	sort.SliceStable(routes, func(i, j int) bool { return routes[i].SortOrder < routes[j].SortOrder })
	for _, r := range routes {
		if r.AcquisitionRouteType != acquisitionRouteQuest || model.PossessionType(r.PossessionType) != model.PossessionTypeMaterial {
			continue
		}
		c.Materials[r.RouteId] = append(c.Materials[r.RouteId], ListedMaterial{r.PossessionId, rarity[r.PossessionId]})
	}

	for _, p := range t.parts {
		k := PartsKind{p.PartsGroupId, p.RarityType}
		c.Parts[p.PartsId] = k
		if id, ok := c.PartsFor[k]; !ok || p.PartsId < id {
			c.PartsFor[k] = p.PartsId
		}
	}

	series := map[int32][]int32{}
	for _, g := range t.partsGroups {
		series[g.PartsSeriesId] = append(series[g.PartsSeriesId], g.PartsGroupId)
	}
	for _, groups := range series {
		sort.Slice(groups, func(i, j int) bool { return groups[i] < groups[j] })
		for start := 0; start+3 <= len(groups); start += 3 {
			set := groups[start : start+3 : start+3]
			for _, g := range set {
				c.SetOf[g] = set
			}
		}
	}
	return c
}
