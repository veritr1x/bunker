package store

import (
	"maps"
	"reflect"
	"slices"
)

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
	Pvp                 PvpState                        `json:"pvp"`
}

// PvpState is the player's Arena: points, battle points, the computer
// opponents offered, logs and weekly results (see internal/pvp).
type PvpState struct {
	SeasonId           int32             `json:"seasonId,omitempty"`
	Point              int32             `json:"point,omitempty"`
	WeekVersion        int64             `json:"weekVersion,omitempty"` // start of the week Point counts for
	MaxSeasonRank      int32             `json:"maxSeasonRank,omitempty"`
	BattlePointMilli   int32             `json:"battlePointMilli,omitempty"`
	BattlePointUpdated int64             `json:"battlePointUpdated,omitempty"` // 0: never used, so full
	WinStreak          int32             `json:"winStreak,omitempty"`
	WinStreakUpdated   int64             `json:"winStreakUpdated,omitempty"`
	DefenseDeckNumber  int32             `json:"defenseDeckNumber,omitempty"`
	DefenseDeckPower   int32             `json:"defenseDeckPower,omitempty"`
	DefenseChecked     int64             `json:"defenseChecked,omitempty"` // defense battles are simulated up to here
	Matching           []int64           `json:"matching,omitempty"`       // computer players offered
	Opponent           int64             `json:"opponent,omitempty"`       // battle started, not finished
	AttackLog          []PvpLog          `json:"attackLog,omitempty"`      // newest first
	DefenseLog         []PvpLog          `json:"defenseLog,omitempty"`
	Season             PvpSeasonStats    `json:"season"`
	Weekly             []PvpWeeklyResult `json:"weekly,omitempty"`            // oldest first
	RewardWeekVersion  int64             `json:"rewardWeekVersion,omitempty"` // weekly rewards paid up to this week
	RewardSeasonId     int32             `json:"rewardSeasonId,omitempty"`
	LatestVersion      int64             `json:"latestVersion,omitempty"`
}

type PvpLog struct {
	PlayerId    int64 `json:"playerId"`
	Point       int32 `json:"point"` // the opponent's points
	Victory     bool  `json:"victory"`
	Datetime    int64 `json:"datetime"`
	Fluctuation int32 `json:"fluctuation"` // the player's point change
}

type PvpSeasonStats struct {
	AttackWins    int32 `json:"attackWins,omitempty"`
	AttackLosses  int32 `json:"attackLosses,omitempty"`
	AttackPoint   int32 `json:"attackPoint,omitempty"`
	DefenseWins   int32 `json:"defenseWins,omitempty"`
	DefenseLosses int32 `json:"defenseLosses,omitempty"`
	DefensePoint  int32 `json:"defensePoint,omitempty"`
}

type PvpWeeklyResult struct {
	WeekVersion int64 `json:"weekVersion"`
	SeasonId    int32 `json:"seasonId"`
	GroupId     int32 `json:"groupId"`
	FinalPoint  int32 `json:"finalPoint"`
	FinalRank   int32 `json:"finalRank"`
}

func (p PvpState) Clone() PvpState {
	out := p
	out.Matching = slices.Clone(p.Matching)
	out.AttackLog = slices.Clone(p.AttackLog)
	out.DefenseLog = slices.Clone(p.DefenseLog)
	out.Weekly = slices.Clone(p.Weekly)
	return out
}

func (p PvpState) Equal(o PvpState) bool { return reflect.DeepEqual(p, o) }

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
	out.Pvp = e.Pvp.Clone()
	return out
}

func (e ExtState) Equal(o ExtState) bool {
	return e.MissionsVersion == o.MissionsVersion && e.DailyGroupReward == o.DailyGroupReward &&
		maps.Equal(e.MissionPass, o.MissionPass) &&
		maps.Equal(e.SceneChoices, o.SceneChoices) &&
		maps.Equal(e.SceneChoiceHistory, o.SceneChoiceHistory) &&
		maps.Equal(e.LevelBonusConfirmed, o.LevelBonusConfirmed) &&
		e.Pvp.Equal(o.Pvp)
}
