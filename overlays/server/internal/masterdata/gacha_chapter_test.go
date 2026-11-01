package masterdata

import (
	"os"
	"testing"

	"lunar-tear/server/internal/masterdata/memorydb"
	"lunar-tear/server/internal/model"
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
