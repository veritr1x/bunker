package store

import (
	"reflect"
	"slices"
)

// QuestExtState is Bunker's quest save data the Lunar Tear schema has no room
// for: the battle record of the quest run in progress (quest missions are
// judged against it) and the Recollections of Dusk deck locks.
type QuestExtState struct {
	Battle                 QuestBattleState         `json:"battle"`
	LimitContentRestricted []LimitContentRestricted `json:"limitContentRestricted,omitempty"`
}

// QuestBattleState is the BattleDetail of every FinishWave since the quest
// started: counts are summed over the waves, maxima kept, and the HP of the
// party at the end of the latest wave. DeckType/DeckNumber are the deck the
// waves were fought with (StartWave's player party).
type QuestBattleState struct {
	DeckType               int32           `json:"deckType,omitempty"`
	DeckNumber             int32           `json:"deckNumber,omitempty"`
	Waves                  int32           `json:"waves,omitempty"`
	CharacterDeathCount    int32           `json:"characterDeathCount,omitempty"`
	MaxDamage              int32           `json:"maxDamage,omitempty"`
	CostumeSkillUseCount   int32           `json:"costumeSkillUseCount,omitempty"`
	WeaponSkillUseCount    int32           `json:"weaponSkillUseCount,omitempty"`
	CompanionSkillUseCount int32           `json:"companionSkillUseCount,omitempty"`
	CriticalCount          int32           `json:"criticalCount,omitempty"`
	MaxComboCount          int32           `json:"maxComboCount,omitempty"`
	ComboMaxDamage         int32           `json:"comboMaxDamage,omitempty"`
	TotalRecoverPoint      int64           `json:"totalRecoverPoint,omitempty"`
	LastWaveHp             []BattleHpState `json:"lastWaveHp,omitempty"`
}

type BattleHpState struct {
	MaxHp       int64 `json:"maxHp"`
	RemainingHp int64 `json:"remainingHp"`
}

// LimitContentRestricted is one IUserDeckLimitContentRestricted row: a costume
// or weapon used in a Recollections of Dusk quest, locked for the rest of the
// chapter's run.
type LimitContentRestricted struct {
	EventQuestChapterId int32  `json:"eventQuestChapterId"`
	QuestId             int32  `json:"questId"`
	DeckRestrictedUuid  string `json:"deckRestrictedUuid"`
	PossessionType      int32  `json:"possessionType"`
	TargetUuid          string `json:"targetUuid"`
	LatestVersion       int64  `json:"latestVersion"`
}

func (q QuestExtState) Clone() QuestExtState {
	out := q
	out.Battle.LastWaveHp = slices.Clone(q.Battle.LastWaveHp)
	out.LimitContentRestricted = slices.Clone(q.LimitContentRestricted)
	return out
}

func (q QuestExtState) Equal(o QuestExtState) bool { return reflect.DeepEqual(q, o) }
