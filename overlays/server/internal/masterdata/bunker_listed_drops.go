package masterdata

import (
	"log"
	"slices"
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

const (
	acquisitionRouteQuest  = 1
	acquisitionRouteSummon = 3
	eventQuestTypeDungeon  = 3
)

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
	// ChapterShown is the memoirs on the screens of a quest's event chapters
	// (m_event_quest_display_item_group): their sets complete like the ones
	// the quest's own drops show.
	ChapterShown map[int32][]int32 // original quest id -> parts ids, ascending
	// Dungeon is the quests of the memory dungeons (event quest type 3), whose
	// higher floors dropped higher rarities of the sets they show.
	Dungeon map[int32]bool
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
	t.chapters, err = utils.ReadTable[EntityMEventQuestChapter]("m_event_quest_chapter")
	read("m_event_quest_chapter")
	t.display, err = utils.ReadTable[EntityMEventQuestDisplayItemGroup]("m_event_quest_display_item_group")
	read("m_event_quest_display_item_group")
	t.seqGroups, err = utils.ReadTable[EntityMEventQuestSequenceGroup]("m_event_quest_sequence_group")
	read("m_event_quest_sequence_group")
	t.sequences, err = utils.ReadTable[EntityMEventQuestSequence]("m_event_quest_sequence")
	read("m_event_quest_sequence")
	return listedDropCatalog(t)
})

type listedDropTables struct {
	routes      []EntityMPossessionAcquisitionRoute
	materials   []EntityMMaterial
	parts       []EntityMParts
	partsGroups []EntityMPartsGroup
	chapters    []EntityMEventQuestChapter
	display     []EntityMEventQuestDisplayItemGroup
	seqGroups   []EntityMEventQuestSequenceGroup
	sequences   []EntityMEventQuestSequence
}

func listedDropCatalog(t listedDropTables) ListedDropCatalog {
	c := ListedDropCatalog{
		Materials: map[int32][]ListedMaterial{},
		Parts:     map[int32]PartsKind{},
		SetOf:     map[int32][]int32{},
		PartsFor:  map[PartsKind]int32{},

		ChapterShown: map[int32][]int32{},
		Dungeon:      map[int32]bool{},
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

	shown := map[int32][]int32{}
	for _, d := range t.display {
		if model.PossessionType(d.PossessionType) == model.PossessionTypeParts {
			shown[d.EventQuestDisplayItemGroupId] = append(shown[d.EventQuestDisplayItemGroupId], d.PossessionId)
		}
	}
	sequenceQuests := map[int32][]int32{}
	for _, s := range t.sequences {
		sequenceQuests[s.EventQuestSequenceId] = append(sequenceQuests[s.EventQuestSequenceId], s.QuestId)
	}
	groupSequences := map[int32][]int32{}
	for _, g := range t.seqGroups {
		groupSequences[g.EventQuestSequenceGroupId] = append(groupSequences[g.EventQuestSequenceGroupId], g.EventQuestSequenceId)
	}
	for _, ch := range t.chapters {
		memoirs := shown[ch.EventQuestDisplayItemGroupId]
		for _, seq := range groupSequences[ch.EventQuestSequenceGroupId] {
			for _, q := range sequenceQuests[seq] {
				if ch.EventQuestType == eventQuestTypeDungeon {
					c.Dungeon[q] = true
				}
				if len(memoirs) > 0 {
					c.ChapterShown[q] = append(c.ChapterShown[q], memoirs...)
				}
			}
		}
	}
	for q, ids := range c.ChapterShown {
		sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
		c.ChapterShown[q] = slices.Compact(ids)
	}
	return c
}
