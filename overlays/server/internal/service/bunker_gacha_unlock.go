package service

import (
	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// bunkerGachaUnlockedFor evaluates Bunker's own unlock conditions; handled is
// false for the game's.
func bunkerGachaUnlockedFor(entry store.GachaCatalogEntry, user *store.UserState) (unlocked, handled bool) {
	switch entry.UnlockConditionType {
	case model.GachaUnlockDarkMemories:
		return user.Tutorials[int32(model.TutorialTypeEndContents)].ProgressPhase >= model.TutorialPhaseEndContentsFirst, true
	}
	return false, false
}

// bunkerGachaUnlockCondition is what the game is sent for Bunker's own
// conditions: none (a locked summon is left out of the list instead).
func bunkerGachaUnlockCondition(entry store.GachaCatalogEntry) (*pb.GachaUnlockCondition, bool) {
	if entry.UnlockConditionType == model.GachaUnlockDarkMemories {
		return &pb.GachaUnlockCondition{GachaUnlockConditionType: model.GachaUnlockNone}, true
	}
	return nil, false
}
