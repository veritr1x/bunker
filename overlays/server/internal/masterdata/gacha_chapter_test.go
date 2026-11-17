package masterdata

import (
	"os"
	"reflect"
	"strings"
	"testing"

	"lunar-tear/server/internal/masterdata/memorydb"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// Runs against real game data: BUNKER_TEST_MASTER is a master data file.
func loadTestMaster(t *testing.T) {
	t.Helper()
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	if err := memorydb.Init(master); err != nil {
		t.Fatal(err)
	}
}

// The Dark Memory summon opens with Dark Memories themselves: the game's
// CalculatorEndContents.IsUnlockEndContents is the END_CONTENTS tutorial at
// EndContentsFirst, which the unlock scene after the first Hard chapter writes.
// (Quest 121 opens Recollections of Dusk, not Dark Memories.)
func TestDarkMemorySummonUnlocksWithDarkMemories(t *testing.T) {
	loadTestMaster(t)
	tickets, err := LoadChapterTickets()
	if err != nil {
		t.Fatal(err)
	}
	var ex *ChapterTicket
	for i := range tickets {
		if tickets[i].AssetName == chapterGachaExAssetName {
			ex = &tickets[i]
		}
	}
	if ex == nil {
		t.Fatal("no Dark Memory chapter summon")
	}
	e := chapterGachaEntry(*ex)
	if e.UnlockConditionType != model.GachaUnlockDarkMemories {
		t.Errorf("Dark Memory summon unlock = %d/%d, want Dark Memories unlocked", e.UnlockConditionType, e.UnlockConditionValue)
	}
}

// Its "To Quests" jumps to RelatedMainQuestChapterId when there is no event
// chapter, and main quest chapter 0 left the game on an empty Quests screen;
// so it names the first Dark Memory chapter.
func TestDarkMemorySummonLinksToDarkMemories(t *testing.T) {
	loadTestMaster(t)
	tickets, err := LoadChapterTickets()
	if err != nil {
		t.Fatal(err)
	}
	for _, ticket := range tickets {
		if ticket.AssetName != chapterGachaExAssetName {
			continue
		}
		if e := chapterGachaEntry(ticket); e.RelatedEventQuestChapterId != 99001 {
			t.Fatalf("Dark Memory summon links to event chapter %d, want 99001", e.RelatedEventQuestChapterId)
		}
		return
	}
	t.Fatal("no Dark Memory chapter summon")
}

func TestChapterBoxGetsListedMaterials(t *testing.T) {
	const a, b, c = 100, 200, 300
	box := []store.GachaBoxContent{{PossessionType: 5, PossessionId: a, RarityType: 10, Count: 10, IsTarget: true}}
	got := withListed(box, []int32{a, b, c}, map[int32]int32{a: 10, b: 30, c: 99})
	want := []store.GachaBoxContent{
		{PossessionType: 5, PossessionId: b, RarityType: 30, Count: 3, IsTarget: true},
		{PossessionType: 5, PossessionId: a, RarityType: 10, Count: 10},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v\nwant %+v", got, want)
	}
	if !box[0].IsTarget {
		t.Fatal("the input box was changed")
	}
}

// Every material the game lists for a chapter summon (m_possession_acquisition_route,
// "3/<asset>/...") is in that summon's box.
func TestChapterSummonsHoldTheirListedItemsOnTheGameData(t *testing.T) {
	loadTestMaster(t)
	tickets, err := LoadChapterTickets()
	if err != nil {
		t.Fatal(err)
	}
	box := map[string]map[int32]bool{}
	for _, tk := range tickets {
		box[tk.AssetName] = map[int32]bool{}
		for _, c := range tk.Box {
			box[tk.AssetName][c.PossessionId] = true
		}
	}
	routes, _ := utils.ReadTable[EntityMPossessionAcquisitionRoute]("m_possession_acquisition_route")
	listed, missing := 0, 0
	for _, r := range routes {
		if r.AcquisitionRouteType != 3 || !strings.HasPrefix(r.RelationValue, "3/") || r.PossessionType != 5 {
			continue
		}
		listed++
		asset := strings.Split(r.RelationValue, "/")[1]
		if !box[asset][r.PossessionId] {
			if missing++; missing <= 5 {
				t.Errorf("%s lacks material %d", asset, r.PossessionId)
			}
		}
	}
	if listed == 0 || missing != 0 {
		t.Fatalf("%d listed, %d missing", listed, missing)
	}
}
