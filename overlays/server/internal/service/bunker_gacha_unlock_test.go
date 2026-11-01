package service

import (
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func darkMemorySummon() store.GachaCatalogEntry {
	return store.GachaCatalogEntry{GachaId: 1, IsUserGachaUnlock: true, UnlockConditionType: model.GachaUnlockDarkMemories}
}

func TestDarkMemorySummonOpensWithDarkMemories(t *testing.T) {
	entry := darkMemorySummon()
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	user.Quests[121] = store.UserQuestState{QuestId: 121, QuestStateType: model.UserQuestStateTypeCleared, ClearCount: 1}
	if gachaUnlockedFor(entry, user) {
		t.Fatal("open after quest 121 without Dark Memories")
	}
	user.Tutorials[int32(model.TutorialTypeEndContents)] = store.TutorialProgressState{TutorialType: int32(model.TutorialTypeEndContents), ProgressPhase: model.TutorialPhaseEndContentsFirst}
	if !gachaUnlockedFor(entry, user) {
		t.Fatal("still locked once Dark Memories are unlocked")
	}
}

// The game is never sent Bunker's own condition.
func TestDarkMemorySummonSendsNoCondition(t *testing.T) {
	if c := gachaUnlockCondition(darkMemorySummon()); c.GachaUnlockConditionType != model.GachaUnlockNone {
		t.Fatalf("sent condition %d, want none", c.GachaUnlockConditionType)
	}
}
