package service

import (
	"testing"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
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

// An event summon is listed while one of its event's runs is on, and its To
// Quests opens that run's chapter row.
func TestEventSummonListedDuringARunAndLinksToIt(t *testing.T) {
	now := int64(1_500)
	gachaNow = func() int64 { return now }
	defer func() { gachaNow = gametime.NowMillis }()
	masterdata.SetEventSummonRunsForTest(340001, map[int32][2]int64{340: {1_000, 2_000}, 10000340: {900_000_000, 950_000_000}})
	entry := store.GachaCatalogEntry{GachaId: 340001, IsUserGachaUnlock: true, UnlockConditionType: model.GachaUnlockEventRun, RelatedEventQuestChapterId: 340}
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	if !gachaUnlockedFor(entry, user) {
		t.Fatal("closed during its run")
	}
	if c := gachaUnlockCondition(entry); c.GachaUnlockConditionType != model.GachaUnlockNone {
		t.Fatalf("sent condition %d", c.GachaUnlockConditionType)
	}
	now = 920_000_000
	g := toProtoGachaFor(entry, &store.GachaBannerState{}, *user)
	if g.RelatedEventQuestChapterId != 10000340 {
		t.Fatalf("links to %d during the rerun, want 10000340", g.RelatedEventQuestChapterId)
	}
	now = 500_000_000
	if gachaUnlockedFor(entry, user) {
		t.Fatal("open between runs")
	}
}
