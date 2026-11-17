package masterdata

import (
	"os"
	"path/filepath"
	"testing"

	"lunar-tear/server/internal/masterdata/memorydb"
)

// loadBonusTestMaster opens the game data named by BUNKER_TEST_MASTER.
func loadBonusTestMaster(t *testing.T) {
	t.Helper()
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
}

func TestImportantItemDropRatesOnTheGameData(t *testing.T) {
	loadBonusTestMaster(t)
	c, err := LoadImportantItemEffectCatalog()
	if err != nil {
		t.Fatal(err)
	}
	if len(c.DropRates) != 13 {
		t.Fatalf("%d drop rates, want 13", len(c.DropRates))
	}
	byItem := map[int32]ImportantItemDropRate{}
	for _, r := range c.DropRates {
		byItem[r.ImportantItemId] = r
	}
	if byItem[200019].RatePermil != 1000 {
		t.Errorf("Dungeon Drop Rate++: %+v", byItem[200019])
	}
	dark, ok := byItem[200021]
	if !ok || !c.ItemMatches(dark.ItemGroupId, 5, 100001) {
		t.Errorf("Dark Memory Drop Rate+ should target every drop: %+v", dark)
	}
	if c.ItemMatches(byItem[200007].ItemGroupId, 5, 999999) {
		t.Errorf("Wednesday Drop Rate+ targets an item outside its group")
	}
}

func TestQuestBonusExpOnTheGameData(t *testing.T) {
	loadBonusTestMaster(t)
	c, err := LoadQuestBonusCatalog()
	if err != nil {
		t.Fatal(err)
	}
	if e := c.ExpByEffect[105]; e.ExpType != 2 || e.BonusValuePermil != 500 {
		t.Fatalf("effect 105: %+v", e)
	}
}

func TestCollectionBonusesFromTables(t *testing.T) {
	got := collectionBonuses(collectionBonusTables{
		bonuses: []EntityMCostumeCollectionBonus{{CollectionBonusId: 1, CollectionBonusGroupId: 10, CollectionBonusQuestAssignmentGroupId: 20, CollectionBonusEffectId: 30, GroupingId: 5, EndDatetime: 9}},
		groups:  []EntityMCostumeCollectionBonusGroup{{CollectionBonusGroupId: 10, CostumeId: 22}, {CollectionBonusGroupId: 10, CostumeId: 11}},
		effects: []EntityMCollectionBonusEffect{{CollectionBonusEffectId: 30, CollectionBonusEffectType: 2, Amount00: 60, Amount01: 70, Amount02: 80, Amount03: 90, Amount04: 100}},
		assignments: []EntityMCollectionBonusQuestAssignment{
			{CollectionBonusQuestAssignmentId: 2, QuestAssignmentType: 2, MainQuestChapterId: 2},
			{CollectionBonusQuestAssignmentId: 200, QuestAssignmentType: 6},
		},
		assignGroup: []EntityMCollectionBonusQuestAssignmentGroup{{CollectionBonusQuestAssignmentGroupId: 20, CollectionBonusQuestAssignmentId: 2}, {CollectionBonusQuestAssignmentGroupId: 20, CollectionBonusQuestAssignmentId: 200}},
	})
	if len(got) != 1 {
		t.Fatalf("got %+v", got)
	}
	b := got[0]
	if b.EffectType != 2 || b.GroupingId != 5 || b.Amounts != [5]int32{60, 70, 80, 90, 100} || len(b.Costumes) != 2 || b.Costumes[0] != 11 {
		t.Fatalf("bonus %+v", b)
	}
	if len(b.MainChapters) != 1 || !b.MainChapters[2] {
		t.Fatalf("chapters %v, want only main chapter 2", b.MainChapters)
	}
}

func TestCollectionBonusesOnTheGameData(t *testing.T) {
	loadBonusTestMaster(t)
	all := CollectionBonuses()
	if len(all) != 21 {
		t.Fatalf("%d bonuses, want 21", len(all))
	}
	for _, b := range all {
		if len(b.Costumes) < 2 || len(b.Costumes) > 3 {
			t.Errorf("bonus %d has %d costumes", b.Id, len(b.Costumes))
		}
		switch b.EffectType {
		case CollectionBonusCostumeExp, CollectionBonusDropRate, CollectionBonusGold:
		default:
			t.Errorf("bonus %d effect type %d", b.Id, b.EffectType)
		}
	}
	if b := all[0]; b.Id != 201 || !b.MainChapters[2] || !b.MainChapters[3] || len(b.MainChapters) != 2 || b.Amounts[0] != 60 || b.Amounts[4] != 100 {
		t.Errorf("bonus 201: %+v", b)
	}
}

func TestMainQuestChaptersFromTables(t *testing.T) {
	got := mainQuestChapters(mainQuestChapterTables{
		chapters:  []EntityMMainQuestChapter{{MainQuestChapterId: 2, MainQuestSequenceGroupId: 2}},
		groups:    []EntityMMainQuestSequenceGroup{{MainQuestSequenceGroupId: 2, DifficultyType: 1, MainQuestSequenceId: 2}, {MainQuestSequenceGroupId: 2, DifficultyType: 2, MainQuestSequenceId: 1002}},
		sequences: []EntityMMainQuestSequence{{MainQuestSequenceId: 2, QuestId: 20}, {MainQuestSequenceId: 1002, QuestId: 10020}},
		relations: []EntityMQuestRelationMainFlow{{MainFlowQuestId: 20, ReplayFlowQuestId: 30020}},
	})
	for _, q := range []int32{20, 10020, 30020} {
		if got[q] != 2 {
			t.Errorf("quest %d: chapter %d, want 2", q, got[q])
		}
	}
}

func TestMainQuestChaptersOnTheGameData(t *testing.T) {
	loadBonusTestMaster(t)
	m := MainQuestChapters()
	if m[2] != 2 || m[10001] != 2 || m[30001] != 2 {
		t.Fatalf("quest 2 (Normal) %d, 10001 (Hard) %d, 30001 (replay of 2) %d; want chapter 2", m[2], m[10001], m[30001])
	}
	if len(m) < 281+270+270+281 {
		t.Fatalf("%d quests mapped", len(m))
	}
}
