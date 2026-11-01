package service

import (
	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// gachaNow is the clock Bunker's summon conditions read (tests replace it).
var gachaNow = gametime.NowMillis

// bunkerGachaUnlockedFor evaluates Bunker's own unlock conditions; handled is
// false for the game's.
func bunkerGachaUnlockedFor(entry store.GachaCatalogEntry, user *store.UserState) (unlocked, handled bool) {
	switch entry.UnlockConditionType {
	case model.GachaUnlockDarkMemories:
		return user.Tutorials[int32(model.TutorialTypeEndContents)].ProgressPhase >= model.TutorialPhaseEndContentsFirst, true
	case model.GachaUnlockEventRun:
		_, open, _ := masterdata.EventSummonRunAt(entry.GachaId, gachaNow())
		return open, true
	}
	return false, false
}

// bunkerGachaUnlockCondition is what the game is sent for Bunker's own
// conditions: none (a locked summon is left out of the list instead).
func bunkerGachaUnlockCondition(entry store.GachaCatalogEntry) (*pb.GachaUnlockCondition, bool) {
	switch entry.UnlockConditionType {
	case model.GachaUnlockDarkMemories, model.GachaUnlockEventRun:
		return &pb.GachaUnlockCondition{GachaUnlockConditionType: model.GachaUnlockNone}, true
	}
	return nil, false
}

// eventSummonLink points an event summon's To Quests at the run that is on:
// during a rerun the first run's chapter row is closed, and the game then
// fell back to its first event tab.
func eventSummonLink(g *pb.Gacha, entry store.GachaCatalogEntry) {
	if chapter, open, _ := masterdata.EventSummonRunAt(entry.GachaId, gachaNow()); open {
		g.RelatedEventQuestChapterId = chapter
	}
}
