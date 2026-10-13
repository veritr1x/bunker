package questflow

import (
	"log"
	"math/rand/v2"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// questBonusDrops lists the m_quest_bonus extra drops one clear earns with a
// deck, as the client's CalculatorQuestBonus.CreateItemBonusResultDropCellData
// draws them on the result screen: per deck member its character's bonus, its
// costume's bonus at the highest limit-break row it reaches, and the same for
// its main and sub weapons. Rows outside their term are skipped.
func (h *QuestHandler) questBonusDrops(user *store.UserState, questDef masterdata.EntityMQuest, deck store.DeckState, nowMillis int64) []RewardGrant {
	qb := h.QuestBonus
	if qb == nil || questDef.QuestBonusId == 0 {
		return nil
	}
	bonus, ok := qb.BonusById[questDef.QuestBonusId]
	if !ok {
		return nil
	}

	var effectGroups []int32
	for _, dcUuid := range deckCharacterUuids(deck) {
		dc, ok := user.DeckCharacters[dcUuid]
		if !ok {
			continue
		}
		if co, ok := user.Costumes[dc.UserCostumeUuid]; ok {
			if cm, ok := h.CostumeById[co.CostumeId]; ok {
				for _, r := range qb.CharacterGroups[bonus.QuestBonusCharacterGroupId] {
					if r.CharacterId == cm.CharacterId && qb.InTerm(r.QuestBonusTermGroupId, nowMillis) {
						effectGroups = append(effectGroups, r.QuestBonusEffectGroupId)
					}
				}
			}
			best, found := int32(-1), int32(0)
			for _, r := range qb.CostumeSettingGroups[bonus.QuestBonusCostumeSettingGroupId] {
				if r.CostumeId == co.CostumeId && r.LimitBreakCountLowerLimit <= co.LimitBreakCount &&
					r.LimitBreakCountLowerLimit > best && qb.InTerm(r.QuestBonusTermGroupId, nowMillis) {
					best, found = r.LimitBreakCountLowerLimit, r.QuestBonusEffectGroupId
				}
			}
			if found != 0 {
				effectGroups = append(effectGroups, found)
			}
		}
		weapons := append([]string{dc.MainUserWeaponUuid}, user.DeckSubWeapons[dcUuid]...)
		for _, wUuid := range weapons {
			w, ok := user.Weapons[wUuid]
			if !ok {
				continue
			}
			best, found := int32(-1), int32(0)
			for _, r := range qb.WeaponGroups[bonus.QuestBonusWeaponGroupId] {
				if r.WeaponId == w.WeaponId && r.LimitBreakCountLowerLimit <= w.LimitBreakCount &&
					r.LimitBreakCountLowerLimit > best && qb.InTerm(r.QuestBonusTermGroupId, nowMillis) {
					best, found = r.LimitBreakCountLowerLimit, r.QuestBonusEffectGroupId
				}
			}
			if found != 0 {
				effectGroups = append(effectGroups, found)
			}
		}
	}

	var out []RewardGrant
	for _, g := range effectGroups {
		for _, d := range qb.DropRewards(g) {
			out = append(out, RewardGrant{
				PossessionType: model.PossessionType(d.PossessionType),
				PossessionId:   d.PossessionId,
				Count:          d.AdditionalCount,
			})
		}
	}
	return out
}

// grantQuestBonusDrops pays the deck's quest bonus drops for clears clears.
// They are not listed in the response: the client adds them to the result
// itself.
func (h *QuestHandler) grantQuestBonusDrops(user *store.UserState, questDef masterdata.EntityMQuest, deck store.DeckState, clears int32, nowMillis int64) {
	for _, d := range h.questBonusDrops(user, questDef, deck, nowMillis) {
		h.applyRewardPossession(user, d.PossessionType, d.PossessionId, d.Count*clears, nowMillis)
		log.Printf("[QuestBonus] quest=%d type=%d id=%d +%d", questDef.QuestId, d.PossessionType, d.PossessionId, d.Count*clears)
	}
}

// importantItemQuestMatches checks a quest against an important item effect's
// target quest group (ImportantItemEffectTargetQuestGroupType).
func (h *QuestHandler) importantItemQuestMatches(groupId int32, t campaign.QuestTarget) bool {
	ie := h.ImportantItemEffects
	for _, r := range ie.QuestGroups[groupId] {
		v := r.TargetValue
		switch r.ImportantItemEffectTargetQuestGroupType {
		case masterdata.ImportantItemTargetWholeQuest:
			return true
		case masterdata.ImportantItemTargetQuestType:
			if int32(t.QuestType) == v {
				return true
			}
		case masterdata.ImportantItemTargetEventQuestType:
			if t.QuestType == campaign.QuestTypeEventQuest && t.EventQuestType == v {
				return true
			}
		case masterdata.ImportantItemTargetMainQuestChapterId:
			if t.QuestType == campaign.QuestTypeMainQuest && t.ChapterId == v {
				return true
			}
		case masterdata.ImportantItemTargetMainQuestQuestId:
			if t.QuestType == campaign.QuestTypeMainQuest && t.QuestId == v {
				return true
			}
		case masterdata.ImportantItemTargetSubQuestChapterId:
			if t.QuestType == campaign.QuestTypeEventQuest && t.ChapterId == v {
				return true
			}
		case masterdata.ImportantItemTargetSubQuestQuestId:
			if t.QuestType == campaign.QuestTypeEventQuest && t.QuestId == v {
				return true
			}
		case masterdata.ImportantItemTargetMainQuestDifficultyType:
			if t.QuestType == campaign.QuestTypeMainQuest && ie.MainQuestDifficulty[t.QuestId] == v {
				return true
			}
		}
	}
	return false
}

// applyImportantItemDropCounts raises drop counts by the DROP_COUNT effects of
// the important items the player owns (m_important_item_effect_drop_count):
// count * CountPermil / 1000 more of each targeted drop, the fraction paid as
// a chance of one more. DROP_RATE effects need a drop lottery, which Bunker's
// fixed pickup drops do not have.
func (h *QuestHandler) applyImportantItemDropCounts(user *store.UserState, drops []RewardGrant, t campaign.QuestTarget, nowMillis int64, roll func(int64) int64) []RewardGrant {
	ie := h.ImportantItemEffects
	if ie == nil || len(drops) == 0 {
		return drops
	}
	permil := make([]int64, len(drops))
	for _, e := range ie.DropCounts {
		if user.ImportantItems[e.ImportantItemId] <= 0 || nowMillis < e.StartDatetime || nowMillis > e.EndDatetime {
			continue
		}
		if !h.importantItemQuestMatches(e.QuestGroupId, t) {
			continue
		}
		for i, d := range drops {
			if ie.ItemMatches(e.ItemGroupId, int32(d.PossessionType), d.PossessionId) {
				permil[i] += int64(e.CountPermil)
			}
		}
	}
	for i := range drops {
		if permil[i] == 0 || drops[i].Count <= 0 {
			continue
		}
		extra := int64(drops[i].Count) * permil[i]
		add := extra / 1000
		if frac := extra % 1000; frac > 0 && roll(1000) < frac {
			add++
		}
		drops[i].Count += int32(add)
	}
	return drops
}

func randInt64n(n int64) int64 { return rand.Int64N(n) }
