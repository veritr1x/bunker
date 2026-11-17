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
