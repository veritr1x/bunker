package questflow

import "lunar-tear/server/internal/masterdata"

// Quest bonus EXP (m_quest_bonus_exp): a quest's bonus characters earn more
// character EXP when they are in the deck ("Character EXP +50%" in the game's
// text). The raise is the bonus character's own; the rest of the deck earns
// as usual.

// questBonusExpTypeCharacter is m_quest_bonus_exp.ExpType for character EXP,
// the only type in the game data.
const questBonusExpTypeCharacter int32 = 2

// characterExpBonusPermil is the character EXP raise character characterId
// gets on a clear of questDef now, in permil.
func (h *QuestHandler) characterExpBonusPermil(questDef masterdata.EntityMQuest, characterId int32, nowMillis int64) int64 {
	qb := h.QuestBonus
	if qb == nil || questDef.QuestBonusId == 0 {
		return 0
	}
	bonus, ok := qb.BonusById[questDef.QuestBonusId]
	if !ok {
		return 0
	}
	var permil int64
	for _, r := range qb.CharacterGroups[bonus.QuestBonusCharacterGroupId] {
		if r.CharacterId != characterId || !qb.InTerm(r.QuestBonusTermGroupId, nowMillis) {
			continue
		}
		for _, e := range qb.EffectGroups[r.QuestBonusEffectGroupId] {
			if e.QuestBonusType != masterdata.QuestBonusTypeExp {
				continue
			}
			if x, ok := qb.ExpByEffect[e.QuestBonusEffectId]; ok && x.ExpType == questBonusExpTypeCharacter {
				permil += int64(x.BonusValuePermil)
			}
		}
	}
	return permil
}

// withPermil is v raised by permil.
func withPermil(v int32, permil int64) int32 {
	if permil <= 0 {
		return v
	}
	return int32(int64(v) * (1000 + permil) / 1000)
}
