package store

import "maps"

// ExtState is save data Bunker adds on top of the Lunar Tear schema. It is
// stored as one JSON document per user (table user_bunker_ext), so new fields
// need no migration.
type ExtState struct {
	MissionsVersion     int32                           `json:"missionsVersion,omitempty"`
	MissionPass         map[int32]MissionPassPointState `json:"missionPass,omitempty"`
	DailyGroupReward    DailyGroupRewardState           `json:"dailyGroupReward"`
	SceneChoices        map[int32]SceneChoiceState      `json:"sceneChoices,omitempty"`        // by QuestSceneChoiceGroupingId
	SceneChoiceHistory  map[int32]int64                 `json:"sceneChoiceHistory,omitempty"`  // QuestSceneChoiceEffectId -> choice time
	LevelBonusConfirmed map[int32]int32                 `json:"levelBonusConfirmed,omitempty"` // CostumeId -> confirmed bonus level
}

type MissionPassPointState struct {
	MissionPassId                int32 `json:"missionPassId"`
	Point                        int32 `json:"point"`
	PremiumRewardReceivedLevel   int32 `json:"premiumRewardReceivedLevel"`
	NoPremiumRewardReceivedLevel int32 `json:"noPremiumRewardReceivedLevel"`
	LatestVersion                int64 `json:"latestVersion"`
}

type DailyGroupRewardState struct {
	LastRewardReceiveEventQuestDailyGroupId int32 `json:"lastRewardReceiveEventQuestDailyGroupId"`
	LastRewardReceiveDatetime               int64 `json:"lastRewardReceiveDatetime"`
	LatestVersion                           int64 `json:"latestVersion"`
}

type SceneChoiceState struct {
	QuestSceneChoiceGroupingId int32 `json:"questSceneChoiceGroupingId"`
	QuestSceneChoiceEffectId   int32 `json:"questSceneChoiceEffectId"`
	LatestVersion              int64 `json:"latestVersion"`
}

func (e *ExtState) EnsureMaps() {
	if e.MissionPass == nil {
		e.MissionPass = make(map[int32]MissionPassPointState)
	}
	if e.SceneChoices == nil {
		e.SceneChoices = make(map[int32]SceneChoiceState)
	}
	if e.SceneChoiceHistory == nil {
		e.SceneChoiceHistory = make(map[int32]int64)
	}
	if e.LevelBonusConfirmed == nil {
		e.LevelBonusConfirmed = make(map[int32]int32)
	}
}

func (e ExtState) Clone() ExtState {
	out := e
	out.MissionPass = maps.Clone(e.MissionPass)
	out.SceneChoices = maps.Clone(e.SceneChoices)
	out.SceneChoiceHistory = maps.Clone(e.SceneChoiceHistory)
	out.LevelBonusConfirmed = maps.Clone(e.LevelBonusConfirmed)
	return out
}

func (e ExtState) Equal(o ExtState) bool {
	return e.MissionsVersion == o.MissionsVersion && e.DailyGroupReward == o.DailyGroupReward &&
		maps.Equal(e.MissionPass, o.MissionPass) &&
		maps.Equal(e.SceneChoices, o.SceneChoices) &&
		maps.Equal(e.SceneChoiceHistory, o.SceneChoiceHistory) &&
		maps.Equal(e.LevelBonusConfirmed, o.LevelBonusConfirmed)
}
