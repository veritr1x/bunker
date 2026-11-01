package questflow

import (
	"log"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// First-clear rewards are what the story gives: Rion's weapon on quest 2, which
// the chapter 2 loadout tutorial then has the player equip. The original game
// would not summon into a full weapon storage, so a story weapon never met the
// limit there. Bunker sends summons past it to the gift box, and a player who
// summoned that early had Rion's weapon sent there too: the tutorial's Select
// then did nothing. First-clear weapons and parts now always go to the
// inventory, past the possession limit.

func (h *QuestHandler) grantFirstClearReward(user *store.UserState, possType model.PossessionType, possId, count int32, nowMillis int64) {
	switch possType {
	case model.PossessionTypeWeapon, model.PossessionTypeWeaponEnhanced:
		for range max(count, 1) {
			h.Granter.GrantWeapon(user, possId, nowMillis)
		}
	case model.PossessionTypeParts, model.PossessionTypePartsEnhanced:
		for range max(count, 1) {
			h.Granter.GrantParts(user, possId, nowMillis)
		}
	default:
		h.Granter.GrantFull(user, possType, possId, count, nowMillis)
	}
}

// ReturnFirstClearRewardsFromGiftBox moves first-clear weapons that a full
// storage sent to the gift box (before first-clear rewards went past the
// limit) into the inventory, once per weapon the player doesn't own. Only gifts
// "for holding too many items" of quests whose first clear was paid move; a
// summon's overflow stays a gift. Returns how many moved; run at game start.
func (h *QuestHandler) ReturnFirstClearRewardsFromGiftBox(user *store.UserState, nowMillis int64) int {
	if len(user.Gifts.NotReceived) == 0 {
		return 0
	}
	rewarded := make(map[int32]bool)
	for questId, q := range user.Quests {
		if !q.IsRewardGranted {
			continue
		}
		questDef, ok := h.QuestById[questId]
		if !ok {
			continue
		}
		for _, r := range h.FirstClearRewardsByGroupId[h.firstClearRewardGroupId(user, questDef)] {
			if t := model.PossessionType(r.PossessionType); t == model.PossessionTypeWeapon || t == model.PossessionTypeWeaponEnhanced {
				rewarded[r.PossessionId] = true
			}
		}
	}
	owned := make(map[int32]bool)
	for _, w := range user.Weapons {
		owned[w.WeaponId] = true
	}
	moved := 0
	kept := user.Gifts.NotReceived[:0]
	for _, gift := range user.Gifts.NotReceived {
		c := gift.GiftCommon
		t := model.PossessionType(c.PossessionType)
		if c.DescriptionGiftTextId == store.GiftTextOverflow && (t == model.PossessionTypeWeapon || t == model.PossessionTypeWeaponEnhanced) &&
			rewarded[c.PossessionId] && !owned[c.PossessionId] {
			h.Granter.GrantWeapon(user, c.PossessionId, nowMillis)
			owned[c.PossessionId] = true
			moved++
			log.Printf("[questflow] user %d: first-clear weapon %d moved from the gift box to the inventory", user.UserId, c.PossessionId)
			continue
		}
		kept = append(kept, gift)
	}
	user.Gifts.NotReceived = kept
	if moved > 0 {
		live := int32(0)
		for _, gift := range kept {
			if gift.ExpirationDatetime == 0 || gift.ExpirationDatetime >= nowMillis {
				live++
			}
		}
		user.Notifications.GiftNotReceiveCount = live
	}
	return moved
}
