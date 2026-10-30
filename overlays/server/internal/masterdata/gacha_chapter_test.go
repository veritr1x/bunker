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

// The Dark Memory summon's "To Quests" opens the Dark Memory quests, which
// stop the game on an empty screen while they are locked; so the summon
// unlocks with them (Season 1 Chapter 14's last quest).
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
	if ex.UnlockQuestId != 121 {
		t.Errorf("Dark Memory summon unlock quest = %d, want 121", ex.UnlockQuestId)
	}
	e := chapterGachaEntry(*ex)
	if e.UnlockConditionType != model.GachaUnlockMainQuestClear || e.UnlockConditionValue != 121 {
		t.Errorf("Dark Memory summon unlock = %d/%d, want main quest clear 121", e.UnlockConditionType, e.UnlockConditionValue)
	}
}
