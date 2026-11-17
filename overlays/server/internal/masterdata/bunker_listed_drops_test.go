package masterdata

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"lunar-tear/server/internal/masterdata/memorydb"
	"lunar-tear/server/internal/utils"
)

func TestListedDropCatalogFromTables(t *testing.T) {
	const material, quest, shop = 5, 1, 2
	c := listedDropCatalog(listedDropTables{
		routes: []EntityMPossessionAcquisitionRoute{
			{PossessionType: material, PossessionId: 300001, AcquisitionRouteType: quest, RouteId: 10, SortOrder: 2},
			{PossessionType: material, PossessionId: 100001, AcquisitionRouteType: quest, RouteId: 10, SortOrder: 1},
			{PossessionType: material, PossessionId: 100001, AcquisitionRouteType: shop, RouteId: 6001},
			{PossessionType: material, PossessionId: 999, AcquisitionRouteType: quest, RouteId: 11},
		},
		materials: []EntityMMaterial{{MaterialId: 300001, RarityType: 30}, {MaterialId: 100001, RarityType: 10}},
		partsGroups: []EntityMPartsGroup{
			{PartsGroupId: 3, PartsSeriesId: 1}, {PartsGroupId: 1, PartsSeriesId: 1}, {PartsGroupId: 2, PartsSeriesId: 1},
			{PartsGroupId: 7, PartsSeriesId: 1}, {PartsGroupId: 8, PartsSeriesId: 1}, {PartsGroupId: 9, PartsSeriesId: 1},
			{PartsGroupId: 20, PartsSeriesId: 2}, {PartsGroupId: 21, PartsSeriesId: 2}, {PartsGroupId: 22, PartsSeriesId: 2},
		},
		parts: []EntityMParts{
			{PartsId: 102, PartsGroupId: 1, RarityType: 10}, {PartsId: 101, PartsGroupId: 1, RarityType: 10},
			{PartsId: 111, PartsGroupId: 1, RarityType: 20}, {PartsId: 201, PartsGroupId: 2, RarityType: 10},
			{PartsId: 301, PartsGroupId: 3, RarityType: 10},
		},
	})
	if want := []ListedMaterial{{100001, 10}, {300001, 30}}; !reflect.DeepEqual(c.Materials[10], want) {
		t.Fatalf("quest 10 materials %v, want %v", c.Materials[10], want)
	}
	if want := []ListedMaterial{{999, 0}}; !reflect.DeepEqual(c.Materials[11], want) {
		t.Fatalf("quest 11 materials %v, want %v", c.Materials[11], want)
	}
	if got := c.SetOf[2]; !reflect.DeepEqual(got, []int32{1, 2, 3}) {
		t.Fatalf("set of group 2: %v", got)
	}
	if got := c.SetOf[8]; !reflect.DeepEqual(got, []int32{7, 8, 9}) {
		t.Fatalf("set of group 8: %v", got)
	}
	if got := c.PartsFor[PartsKind{1, 10}]; got != 101 {
		t.Fatalf("parts for group 1 rarity 10: %d", got)
	}
	if got := c.Parts[111]; got != (PartsKind{1, 20}) {
		t.Fatalf("kind of 111: %v", got)
	}
}

func TestListedDropsOnTheGameData(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	path := filepath.Join(t.TempDir(), "master.bin.e")
	data, err := os.ReadFile(master)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := memorydb.Init(path); err != nil {
		t.Fatal(err)
	}
	c := ListedDrops()
	total := 0
	for q, ms := range c.Materials {
		total += len(ms)
		for _, m := range ms {
			switch m.Rarity {
			case 10, 20, 30, 40:
			default:
				t.Errorf("quest %d material %d has rarity %d", q, m.MaterialId, m.Rarity)
			}
		}
	}
	if total != 5741 {
		t.Fatalf("%d route-listed quest materials, want 5741", total)
	}
	for g, set := range c.SetOf {
		if len(set) != 3 {
			t.Fatalf("group %d: set %v", g, set)
		}
	}
	pickups, _ := utils.ReadTable[EntityMQuestPickupRewardGroup]("m_quest_pickup_reward_group")
	drops, _ := utils.ReadTable[EntityMBattleDropReward]("m_battle_drop_reward")
	byId := map[int32]EntityMBattleDropReward{}
	for _, d := range drops {
		byId[d.BattleDropRewardId] = d
	}
	shown, missing := 0, 0
	for _, p := range pickups {
		d := byId[p.BattleDropRewardId]
		if d.PossessionType != 4 {
			continue
		}
		shown++
		k, ok := c.Parts[d.PossessionId]
		if !ok {
			t.Fatalf("shown parts %d unknown", d.PossessionId)
		}
		for _, g := range c.SetOf[k.Group] {
			if _, ok := c.PartsFor[PartsKind{g, k.Rarity}]; !ok {
				if missing++; missing <= 5 {
					t.Errorf("parts %d: no parts for group %d at rarity %d", d.PossessionId, g, k.Rarity)
				}
			}
		}
	}
	if shown == 0 || missing != 0 {
		t.Fatalf("%d shown memoirs, %d set pieces with no parts", shown, missing)
	}
}

func TestListedDropCatalogChapterShown(t *testing.T) {
	const parts = 4
	c := listedDropCatalog(listedDropTables{
		chapters: []EntityMEventQuestChapter{
			{EventQuestChapterId: 1, EventQuestDisplayItemGroupId: 10, EventQuestSequenceGroupId: 20},
			{EventQuestChapterId: 2, EventQuestDisplayItemGroupId: 11, EventQuestSequenceGroupId: 21},
		},
		display: []EntityMEventQuestDisplayItemGroup{
			{EventQuestDisplayItemGroupId: 10, PossessionType: parts, PossessionId: 230},
			{EventQuestDisplayItemGroupId: 10, PossessionType: parts, PossessionId: 140},
			{EventQuestDisplayItemGroupId: 10, PossessionType: 6, PossessionId: 1},
			{EventQuestDisplayItemGroupId: 11, PossessionType: parts, PossessionId: 140},
			{EventQuestDisplayItemGroupId: 11, PossessionType: parts, PossessionId: 330},
		},
		seqGroups: []EntityMEventQuestSequenceGroup{{EventQuestSequenceGroupId: 20, EventQuestSequenceId: 30}, {EventQuestSequenceGroupId: 21, EventQuestSequenceId: 31}},
		sequences: []EntityMEventQuestSequence{{EventQuestSequenceId: 30, QuestId: 500}, {EventQuestSequenceId: 30, QuestId: 501}, {EventQuestSequenceId: 31, QuestId: 501}},
	})
	if got := c.ChapterShown[500]; !reflect.DeepEqual(got, []int32{140, 230}) {
		t.Fatalf("quest 500: %v", got)
	}
	if got := c.ChapterShown[501]; !reflect.DeepEqual(got, []int32{140, 230, 330}) {
		t.Fatalf("quest 501: %v", got)
	}
}

func TestListedDropCatalogDungeonQuests(t *testing.T) {
	c := listedDropCatalog(listedDropTables{
		chapters: []EntityMEventQuestChapter{
			{EventQuestChapterId: 1, EventQuestType: 3, EventQuestSequenceGroupId: 20},
			{EventQuestChapterId: 2, EventQuestType: 2, EventQuestSequenceGroupId: 21},
		},
		seqGroups: []EntityMEventQuestSequenceGroup{{EventQuestSequenceGroupId: 20, EventQuestSequenceId: 30}, {EventQuestSequenceGroupId: 21, EventQuestSequenceId: 31}},
		sequences: []EntityMEventQuestSequence{{EventQuestSequenceId: 30, QuestId: 500}, {EventQuestSequenceId: 31, QuestId: 600}},
	})
	if !c.Dungeon[500] || c.Dungeon[600] {
		t.Fatalf("dungeon quests %v", c.Dungeon)
	}
}

// Every memoir the game's drop catalogue holds can be had: a quest shows (in
// its drops or on its chapter screen) a piece of its set at its rarity, a
// memory dungeon shows its set at a lower rarity, or a shop, mission or quest
// reward (first clear, replay, quest mission) gives it.
func TestEveryCatalogueMemoirIsReachableOnTheGameData(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	path := filepath.Join(t.TempDir(), "master.bin.e")
	data, _ := os.ReadFile(master)
	os.WriteFile(path, data, 0o600)
	if err := memorydb.Init(path); err != nil {
		t.Fatal(err)
	}
	c := ListedDrops()
	quests, _ := utils.ReadTable[EntityMQuest]("m_quest")
	pickups, _ := utils.ReadTable[EntityMQuestPickupRewardGroup]("m_quest_pickup_reward_group")
	drops, _ := utils.ReadTable[EntityMBattleDropReward]("m_battle_drop_reward")
	shops, _ := utils.ReadTable[EntityMShopItemContentPossession]("m_shop_item_content_possession")
	missions, _ := utils.ReadTable[EntityMMissionReward]("m_mission_reward")
	byId := map[int32]EntityMBattleDropReward{}
	for _, d := range drops {
		byId[d.BattleDropRewardId] = d
	}
	group := map[int32][]int32{}
	for _, p := range pickups {
		group[p.QuestPickupRewardGroupId] = append(group[p.QuestPickupRewardGroupId], p.BattleDropRewardId)
	}
	type setAt struct{ first, rarity int32 }
	reach := map[setAt]bool{}
	for _, q := range quests {
		ids := append([]int32(nil), c.ChapterShown[q.QuestId]...)
		for _, b := range group[q.QuestPickupRewardGroupId] {
			if d := byId[b]; d.PossessionType == 4 {
				ids = append(ids, d.PossessionId)
			}
		}
		top := map[int32]int32{} // the dungeon steps up from the quest's own drops
		for i, id := range ids {
			k, ok := c.Parts[id]
			if !ok || len(c.SetOf[k.Group]) == 0 {
				continue
			}
			first := c.SetOf[k.Group][0]
			reach[setAt{first, k.Rarity}] = true
			if i >= len(c.ChapterShown[q.QuestId]) {
				top[first] = max(top[first], k.Rarity)
			}
		}
		if c.Dungeon[q.QuestId] {
			for first, r := range top {
				for up := r + 10; up <= 40; up += 10 {
					reach[setAt{first, up}] = true
				}
			}
		}
	}
	other := map[int32]bool{} // parts ids; compared by kind below (a piece's ranks share it)
	for _, s := range shops {
		if s.PossessionType == 4 {
			other[s.PossessionId] = true
		}
	}
	for _, m := range missions {
		if m.PossessionType == 4 {
			other[m.PossessionId] = true
		}
	}
	firsts, _ := utils.ReadTable[EntityMQuestFirstClearRewardGroup]("m_quest_first_clear_reward_group")
	for _, r := range firsts {
		if r.PossessionType == 4 {
			other[r.PossessionId] = true
		}
	}
	replays, _ := utils.ReadTable[EntityMQuestReplayFlowRewardGroup]("m_quest_replay_flow_reward_group")
	for _, r := range replays {
		if r.PossessionType == 4 {
			other[r.PossessionId] = true
		}
	}
	questMissions, _ := utils.ReadTable[EntityMQuestMissionReward]("m_quest_mission_reward")
	for _, r := range questMissions {
		if r.PossessionType == 4 {
			other[r.PossessionId] = true
		}
	}
	otherKinds := map[PartsKind]bool{}
	for id := range other {
		otherKinds[c.Parts[id]] = true
	}
	missing := 0
	for _, d := range drops {
		k, ok := c.Parts[d.PossessionId]
		if d.PossessionType != 4 || !ok || otherKinds[k] || len(c.SetOf[k.Group]) == 0 {
			continue
		}
		if !reach[setAt{c.SetOf[k.Group][0], k.Rarity}] {
			if missing++; missing <= 5 {
				t.Errorf("memoir %d (group %d, rarity %d) can't be had", d.PossessionId, k.Group, k.Rarity)
			}
		}
	}
	if missing != 0 {
		t.Fatalf("%d catalogue memoirs can't be had", missing)
	}
}
