package questflow

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
)

func expBonusHandler() *QuestHandler {
	h := testHandler()
	h.QuestBonus = &masterdata.QuestBonusCatalog{
		BonusById: map[int32]masterdata.EntityMQuestBonus{9: {QuestBonusId: 9, QuestBonusCharacterGroupId: 301}},
		CharacterGroups: map[int32][]masterdata.EntityMQuestBonusCharacterGroup{301: {
			{CharacterId: 1001, QuestBonusEffectGroupId: 1031},
			{CharacterId: 1002, QuestBonusEffectGroupId: 1031, QuestBonusTermGroupId: 5},
		}},
		EffectGroups: map[int32][]masterdata.EntityMQuestBonusEffectGroup{
			1031: {{QuestBonusType: masterdata.QuestBonusTypeExp, QuestBonusEffectId: 105}},
		},
		ExpByEffect:  map[int32]masterdata.EntityMQuestBonusExp{105: {QuestBonusEffectId: 105, ExpType: 2, BonusValuePermil: 500}},
		TermsByGroup: map[int32][]masterdata.EntityMQuestBonusTermGroup{5: {{StartDatetime: 100, EndDatetime: 200}}},
	}
	return h
}

func TestCharacterExpBonusForTheBonusCharacter(t *testing.T) {
	h := expBonusHandler()
	quest := masterdata.EntityMQuest{QuestId: testQuest, QuestBonusId: 9}
	if got := h.characterExpBonusPermil(quest, 1001, 0); got != 500 {
		t.Fatalf("bonus character: %d, want 500", got)
	}
	if got := h.characterExpBonusPermil(quest, 1003, 0); got != 0 {
		t.Fatalf("other character: %d", got)
	}
	if got := h.characterExpBonusPermil(masterdata.EntityMQuest{QuestId: testQuest}, 1001, 0); got != 0 {
		t.Fatalf("quest without a bonus: %d", got)
	}
}

func TestCharacterExpBonusOutOfTerm(t *testing.T) {
	h := expBonusHandler()
	quest := masterdata.EntityMQuest{QuestId: testQuest, QuestBonusId: 9}
	if got := h.characterExpBonusPermil(quest, 1002, 0); got != 0 {
		t.Fatalf("out of term: %d", got)
	}
	if got := h.characterExpBonusPermil(quest, 1002, 150); got != 500 {
		t.Fatalf("in term: %d", got)
	}
}

func TestWithPermil(t *testing.T) {
	if got := withPermil(300, 500); got != 450 {
		t.Fatalf("300 +500‰ = %d", got)
	}
	if got := withPermil(7, 0); got != 7 {
		t.Fatalf("no bonus = %d", got)
	}
}
