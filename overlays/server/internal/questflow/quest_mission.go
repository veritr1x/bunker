package questflow

import (
	"log"
	"slices"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Quest missions are judged by the server at a winning finish, against the
// deck the waves were fought with and the BattleDetail stats the client sent
// with each FinishWave (store.QuestBattleState). Condition semantics follow
// the client's QuestMissionConditionType names and the m_quest_mission rows;
// a type not handled here clears on any win.

// ResetBattleStats forgets the previous run's battle record; called when a
// quest run starts (not on a restart, which resumes the same run).
func ResetBattleStats(user *store.UserState) {
	user.Ext.Quest.Battle = store.QuestBattleState{}
}

// RecordStartWave notes the player's deck from StartWave's party list.
func RecordStartWave(user *store.UserState, parties []*pb.UserPartyInitialInfo) {
	for _, p := range parties {
		if p == nil || p.UserDeckNumber == 0 {
			continue
		}
		user.Ext.Quest.Battle.DeckType = p.DeckType
		user.Ext.Quest.Battle.DeckNumber = int32(p.UserDeckNumber)
		return
	}
}

// RecordFinishWave adds one wave's BattleDetail to the run's record. The
// client fills it per wave (TurnBattleWavePlayerLogCache), so counts are
// summed and maxima kept; HP is the party's at the end of the latest wave.
func RecordFinishWave(user *store.UserState, d *pb.BattleDetail) {
	if d == nil {
		return
	}
	b := &user.Ext.Quest.Battle
	b.Waves++
	b.CharacterDeathCount += d.CharacterDeathCount
	b.MaxDamage = max(b.MaxDamage, d.MaxDamage)
	b.CostumeSkillUseCount += d.PlayerCostumeActiveSkillUsedCount
	b.WeaponSkillUseCount += d.PlayerWeaponActiveSkillUsedCount
	b.CompanionSkillUseCount += d.PlayerCompanionSkillUsedCount
	b.CriticalCount += d.CriticalCount
	b.MaxComboCount = max(b.MaxComboCount, d.ComboCount)
	b.ComboMaxDamage = max(b.ComboMaxDamage, d.ComboMaxDamage)
	b.TotalRecoverPoint += d.TotalRecoverPoint
	b.LastWaveHp = nil
	for _, c := range d.CostumeBattleInfo {
		if c == nil {
			continue
		}
		b.LastWaveHp = append(b.LastWaveHp, store.BattleHpState{MaxHp: c.MaxHp, RemainingHp: c.RemainingHp})
	}
}

// missionUnit is one deck member as quest missions see it.
type missionUnit struct {
	characterId         int32
	costumeId           int32
	costumeRarity       int32
	skillfulWeaponType  int32
	mainWeaponAttribute int32
	mainWeaponRarity    int32
	weaponAttributes    []int32 // main and sub weapons
	companionId         int32
}

type missionDeck struct {
	units []missionUnit
	power int32
}

// battleDeck finds the deck the quest was fought with: StartWave's party,
// else the quest's deck number.
func battleDeck(user *store.UserState, questId int32) (store.DeckState, bool) {
	if b := user.Ext.Quest.Battle; b.DeckNumber != 0 {
		if d, ok := user.Decks[store.DeckKey{DeckType: model.DeckType(b.DeckType), UserDeckNumber: b.DeckNumber}]; ok {
			return d, true
		}
	}
	dn := user.Quests[questId].UserDeckNumber
	if dn == 0 {
		return store.DeckState{}, false
	}
	for _, dt := range []model.DeckType{model.DeckTypeQuest, model.DeckTypeRestrictedQuest, model.DeckTypeRestrictedLimitContentQuest} {
		if d, ok := user.Decks[store.DeckKey{DeckType: dt, UserDeckNumber: dn}]; ok {
			return d, true
		}
	}
	return store.DeckState{}, false
}

func deckCharacterUuids(d store.DeckState) []string {
	var out []string
	for _, id := range []string{d.UserDeckCharacterUuid01, d.UserDeckCharacterUuid02, d.UserDeckCharacterUuid03} {
		if id != "" {
			out = append(out, id)
		}
	}
	return out
}

func (h *QuestHandler) missionDeckFor(user *store.UserState, questId int32) missionDeck {
	d, ok := battleDeck(user, questId)
	if !ok {
		return missionDeck{}
	}
	md := missionDeck{power: d.Power}
	for _, dcUuid := range deckCharacterUuids(d) {
		dc, ok := user.DeckCharacters[dcUuid]
		if !ok || dc.UserCostumeUuid == "" {
			continue
		}
		var u missionUnit
		if co, ok := user.Costumes[dc.UserCostumeUuid]; ok {
			u.costumeId = co.CostumeId
			if cm, ok := h.CostumeById[co.CostumeId]; ok {
				u.characterId = cm.CharacterId
				u.costumeRarity = cm.RarityType
				u.skillfulWeaponType = cm.SkillfulWeaponType
			}
		}
		if w, ok := user.Weapons[dc.MainUserWeaponUuid]; ok {
			if wm, ok := h.WeaponById[w.WeaponId]; ok {
				u.mainWeaponAttribute = wm.AttributeType
				u.mainWeaponRarity = wm.RarityType
				u.weaponAttributes = append(u.weaponAttributes, wm.AttributeType)
			}
		}
		for _, sub := range user.DeckSubWeapons[dcUuid] {
			if w, ok := user.Weapons[sub]; ok {
				if wm, ok := h.WeaponById[w.WeaponId]; ok {
					u.weaponAttributes = append(u.weaponAttributes, wm.AttributeType)
				}
			}
		}
		if c, ok := user.Companions[dc.UserCompanionUuid]; ok {
			u.companionId = c.CompanionId
		}
		md.units = append(md.units, u)
	}
	return md
}

func anyUnit(units []missionUnit, f func(missionUnit) bool) bool {
	return slices.ContainsFunc(units, f)
}

func allUnits(units []missionUnit, f func(missionUnit) bool) bool {
	if len(units) == 0 {
		return false
	}
	for _, u := range units {
		if !f(u) {
			return false
		}
	}
	return true
}

// containsValues reports whether the deck's values cover all (or any) of want.
func containsValues(units []missionUnit, want []int32, all bool, value func(missionUnit) int32) bool {
	return containsGroup(want, all, func(w int32) bool {
		return anyUnit(units, func(u missionUnit) bool { return value(u) == w })
	})
}

func containsGroup(want []int32, all bool, has func(int32) bool) bool {
	if len(want) == 0 {
		return false
	}
	for _, w := range want {
		if has(w) != all {
			return !all
		}
	}
	return all
}

func compare(a, b int32, op int) bool {
	switch op {
	case 0:
		return a == b
	case 1:
		return a >= b
	default:
		return a <= b
	}
}

// minHpPercentAtLeast reports whether every party member ended the last wave
// at pct% HP or more.
func minHpPercentAtLeast(b store.QuestBattleState, pct int32) bool {
	if len(b.LastWaveHp) == 0 {
		return false
	}
	for _, hp := range b.LastWaveHp {
		if hp.MaxHp <= 0 {
			continue
		}
		if hp.RemainingHp*100 < int64(pct)*hp.MaxHp {
			return false
		}
	}
	return true
}

// missionConditionMet judges one regular quest mission after a win.
func (h *QuestHandler) missionConditionMet(m masterdata.EntityMQuestMission, deck missionDeck, b store.QuestBattleState) bool {
	v := m.ConditionValue
	group := h.MissionConditionValues[m.QuestMissionConditionValueGroupId]
	units := deck.units
	character := func(u missionUnit) int32 { return u.characterId }
	costume := func(u missionUnit) int32 { return u.costumeId }
	skillful := func(u missionUnit) int32 { return u.skillfulWeaponType }
	mainAttr := func(u missionUnit) int32 { return u.mainWeaponAttribute }

	switch ct := model.QuestMissionConditionType(m.QuestMissionConditionType); ct {
	case model.QuestMissionConditionTypeLessThanOrEqualXPeopleNotAlive:
		return b.CharacterDeathCount <= v
	case model.QuestMissionConditionTypeMaxDamage:
		return b.MaxDamage >= v
	case model.QuestMissionConditionTypeSpecifiedCostumeIsInDeck:
		return anyUnit(units, func(u missionUnit) bool { return u.costumeId == v })
	case model.QuestMissionConditionTypeSpecifiedCharacterIsInDeck:
		return anyUnit(units, func(u missionUnit) bool { return u.characterId == v })
	case model.QuestMissionConditionTypeSpecifiedAttributeMainWeaponIsInDeck:
		return anyUnit(units, func(u missionUnit) bool { return u.mainWeaponAttribute == v })
	case model.QuestMissionConditionTypeGreaterThanOrEqualXCostumeSkillUseCount:
		return b.CostumeSkillUseCount >= v
	case model.QuestMissionConditionTypeGreaterThanOrEqualXWeaponSkillUseCount:
		return b.WeaponSkillUseCount >= v
	case model.QuestMissionConditionTypeGreaterThanOrEqualXCompanionSkillUseCount:
		return b.CompanionSkillUseCount >= v
	case model.QuestMissionConditionTypeCostumeSkillfulWeaponAllCharacter:
		return allUnits(units, func(u missionUnit) bool { return u.skillfulWeaponType == v })
	case model.QuestMissionConditionTypeCostumeSkillfulWeaponAnyCharacter:
		return anyUnit(units, func(u missionUnit) bool { return u.skillfulWeaponType == v })
	case model.QuestMissionConditionTypeCostumeRarityEqAllCharacter,
		model.QuestMissionConditionTypeCostumeRarityGeAllCharacter,
		model.QuestMissionConditionTypeCostumeRarityLeAllCharacter:
		op := int(ct - model.QuestMissionConditionTypeCostumeRarityEqAllCharacter)
		return allUnits(units, func(u missionUnit) bool { return compare(u.costumeRarity, v, op) })
	case model.QuestMissionConditionTypeCostumeRarityEqAnyCharacter,
		model.QuestMissionConditionTypeCostumeRarityGeAnyCharacter,
		model.QuestMissionConditionTypeCostumeRarityLeAnyCharacter:
		op := int(ct - model.QuestMissionConditionTypeCostumeRarityEqAnyCharacter)
		return anyUnit(units, func(u missionUnit) bool { return compare(u.costumeRarity, v, op) })
	case model.QuestMissionConditionTypeSpecifiedAttributeWeaponIsInDeck:
		return anyUnit(units, func(u missionUnit) bool { return slices.Contains(u.weaponAttributes, v) })
	case model.QuestMissionConditionTypeSpecifiedAttributeMainWeaponAllCharacter:
		return allUnits(units, func(u missionUnit) bool { return u.mainWeaponAttribute == v })
	case model.QuestMissionConditionTypeWeaponMainRarityEqAllCharacter,
		model.QuestMissionConditionTypeWeaponMainRarityGeAllCharacter,
		model.QuestMissionConditionTypeWeaponMainRarityLeAllCharacter:
		op := int(ct - model.QuestMissionConditionTypeWeaponMainRarityEqAllCharacter)
		return allUnits(units, func(u missionUnit) bool { return compare(u.mainWeaponRarity, v, op) })
	case model.QuestMissionConditionTypeWeaponMainRarityEqAnyCharacter,
		model.QuestMissionConditionTypeWeaponMainRarityGeAnyCharacter,
		model.QuestMissionConditionTypeWeaponMainRarityLeAnyCharacter:
		op := int(ct - model.QuestMissionConditionTypeWeaponMainRarityEqAnyCharacter)
		return anyUnit(units, func(u missionUnit) bool { return compare(u.mainWeaponRarity, v, op) })
	case model.QuestMissionConditionTypeCompanionId:
		return anyUnit(units, func(u missionUnit) bool { return u.companionId == v })
	case model.QuestMissionConditionTypeDeckPowerGe:
		return deck.power >= v
	case model.QuestMissionConditionTypeDeckPowerLe:
		return deck.power <= v
	case model.QuestMissionConditionTypeDeckCostumeNumEq,
		model.QuestMissionConditionTypeDeckCostumeNumGe,
		model.QuestMissionConditionTypeDeckCostumeNumLe:
		return compare(int32(len(units)), v, int(ct-model.QuestMissionConditionTypeDeckCostumeNumEq))
	case model.QuestMissionConditionTypeCriticalCountGe:
		return b.CriticalCount >= v
	case model.QuestMissionConditionTypeMinHpPercentageGe:
		return minHpPercentAtLeast(b, v)
	case model.QuestMissionConditionTypeComboCountGe:
		return b.MaxComboCount >= v
	case model.QuestMissionConditionTypeComboMaxDamageGe:
		return b.ComboMaxDamage >= v
	case model.QuestMissionConditionTypeLessThanOrEqualXCostumeSkillUseCount:
		return b.CostumeSkillUseCount <= v
	case model.QuestMissionConditionTypeLessThanOrEqualXWeaponSkillUseCount:
		return b.WeaponSkillUseCount <= v
	case model.QuestMissionConditionTypeLessThanOrEqualXCompanionSkillUseCount:
		return b.CompanionSkillUseCount <= v
	case model.QuestMissionConditionTypeWithoutRecoverySkill:
		return b.TotalRecoverPoint == 0
	case model.QuestMissionConditionTypeWithoutCostumeSkill:
		return b.CostumeSkillUseCount == 0
	case model.QuestMissionConditionTypeWithoutWeaponSkill:
		return b.WeaponSkillUseCount == 0
	case model.QuestMissionConditionTypeWithoutCompanionSkill:
		return b.CompanionSkillUseCount == 0
	case model.QuestMissionConditionTypeCharacterContainAll, model.QuestMissionConditionTypeCharacterContainAny:
		return containsValues(units, group, ct == model.QuestMissionConditionTypeCharacterContainAll, character)
	case model.QuestMissionConditionTypeCostumeContainAll, model.QuestMissionConditionTypeCostumeContainAny:
		return containsValues(units, group, ct == model.QuestMissionConditionTypeCostumeContainAll, costume)
	case model.QuestMissionConditionTypeCostumeSkillfulWeaponContainAll, model.QuestMissionConditionTypeCostumeSkillfulWeaponContainAny:
		return containsValues(units, group, ct == model.QuestMissionConditionTypeCostumeSkillfulWeaponContainAll, skillful)
	case model.QuestMissionConditionTypeAttributeMainWeaponContainAll, model.QuestMissionConditionTypeAttributeMainWeaponContainAny:
		return containsValues(units, group, ct == model.QuestMissionConditionTypeAttributeMainWeaponContainAll, mainAttr)
	case model.QuestMissionConditionTypeAttributeWeaponContainAll, model.QuestMissionConditionTypeAttributeWeaponContainAny:
		return containsGroup(group, ct == model.QuestMissionConditionTypeAttributeWeaponContainAll, func(w int32) bool {
			return anyUnit(units, func(u missionUnit) bool { return slices.Contains(u.weaponAttributes, w) })
		})
	default:
		log.Printf("[QuestMission] mission %d: condition type %d not judged, cleared on win", m.QuestMissionId, m.QuestMissionConditionType)
		return true
	}
}

// judgeQuestMissions fills the outcome's mission rewards after a win: each
// regular mission not cleared before whose condition this run met pays its
// reward, and the COMPLETE mission pays once every regular mission is cleared.
func (h *QuestHandler) judgeQuestMissions(user *store.UserState, questId int32, outcome *FinishOutcome) {
	missionIds := h.MissionIdsByQuestId[questId]
	if len(missionIds) == 0 {
		return
	}
	deck := h.missionDeckFor(user, questId)
	battle := user.Ext.Quest.Battle

	regular, cleared := 0, 0
	for _, id := range missionIds {
		def, ok := h.MissionById[id]
		if !ok || model.QuestMissionConditionType(def.QuestMissionConditionType) == model.QuestMissionConditionTypeComplete {
			continue
		}
		regular++
		if user.QuestMissions[store.QuestMissionKey{QuestId: questId, QuestMissionId: id}].IsClear {
			cleared++
			continue
		}
		if !h.missionConditionMet(def, deck, battle) {
			continue
		}
		cleared++
		outcome.clearedMissionIds = append(outcome.clearedMissionIds, id)
		outcome.MissionClearRewards = appendMissionRewards(outcome.MissionClearRewards, h.MissionRewardsByMissionId[def.QuestMissionRewardId])
	}
	if regular == 0 || cleared < regular {
		return
	}
	for _, id := range missionIds {
		def, ok := h.MissionById[id]
		if !ok || model.QuestMissionConditionType(def.QuestMissionConditionType) != model.QuestMissionConditionTypeComplete {
			continue
		}
		if user.QuestMissions[store.QuestMissionKey{QuestId: questId, QuestMissionId: id}].IsClear {
			continue
		}
		outcome.clearedMissionIds = append(outcome.clearedMissionIds, id)
		outcome.MissionClearCompleteRewards = appendMissionRewards(outcome.MissionClearCompleteRewards, h.MissionRewardsByMissionId[def.QuestMissionRewardId])
		outcome.BigWinClearedQuestMissionIds = append(outcome.BigWinClearedQuestMissionIds, id)
	}
	outcome.IsBigWin = len(outcome.BigWinClearedQuestMissionIds) > 0
}

// markMissionsCleared records the missions a win cleared.
func (h *QuestHandler) markMissionsCleared(user *store.UserState, questId int32, missionIds []int32, nowMillis int64) {
	for _, id := range missionIds {
		key := store.QuestMissionKey{QuestId: questId, QuestMissionId: id}
		mission := user.QuestMissions[key]
		mission.QuestId = questId
		mission.QuestMissionId = id
		mission.IsClear = true
		mission.ProgressValue = 1
		mission.LatestClearDatetime = nowMillis
		user.QuestMissions[key] = mission
	}
}
