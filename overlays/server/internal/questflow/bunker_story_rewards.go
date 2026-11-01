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
// summon's overflow stays a gift. Then the default deck gets back a weapon it
// was built without (equipDefaultDeckWeapon). Returns how many moved; run at
// game start.
func (h *QuestHandler) ReturnFirstClearRewardsFromGiftBox(user *store.UserState, nowMillis int64) int {
	moved := h.moveFirstClearWeaponGifts(user, nowMillis)
	for weaponId := range defaultDeckWeaponCostume {
		h.equipDefaultDeckWeapon(user, weaponId, nowMillis)
	}
	return moved
}

// RepairOnGameStart fixes saves made by older versions: story weapons in the
// gift box, the default deck's empty slot, memoirs without a sub-status.
func (h *QuestHandler) RepairOnGameStart(user *store.UserState, nowMillis int64) {
	h.ReturnFirstClearRewardsFromGiftBox(user, nowMillis)
	h.Granter.RepairMemoirSubStatuses(user, nowMillis)
}

func (h *QuestHandler) moveFirstClearWeaponGifts(user *store.UserState, nowMillis int64) int {
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

// The default deck's pairs (store.EnsureDefaultDeck): Rion's costume holds
// Rion's weapon.
var defaultDeckWeaponCostume = map[int32]int32{101001: 10100}

// equipDefaultDeckWeapon gives the weapon to the deck character that
// EnsureDefaultDeck built without it: the loadout tutorial's first step makes
// deck 1 with Rion and Rion's weapon, and with that weapon in the gift box Rion
// got no main weapon, so the tutorial's Select did nothing (even once the
// weapon was back). A weapon owned nowhere (its overflow gift expired after 30
// days) is given again; an empty slot shows it was never had.
func (h *QuestHandler) equipDefaultDeckWeapon(user *store.UserState, weaponId int32, nowMillis int64) {
	costumeId, ok := defaultDeckWeaponCostume[weaponId]
	if !ok {
		return
	}
	slot := ""
	for k, dc := range user.DeckCharacters {
		if dc.MainUserWeaponUuid == "" && user.Costumes[dc.UserCostumeUuid].CostumeId == costumeId {
			slot = k
			break
		}
	}
	if slot == "" {
		return
	}
	weaponUuid := ownedWeaponUuid(user, weaponId)
	if weaponUuid == "" {
		for _, gift := range user.Gifts.NotReceived {
			if gift.GiftCommon.PossessionId == weaponId && model.PossessionType(gift.GiftCommon.PossessionType) == model.PossessionTypeWeapon {
				return // still to be claimed
			}
		}
		h.Granter.GrantWeapon(user, weaponId, nowMillis)
		weaponUuid = ownedWeaponUuid(user, weaponId)
		log.Printf("[questflow] user %d: weapon %d given again (owned nowhere)", user.UserId, weaponId)
	}
	dc := user.DeckCharacters[slot]
	dc.MainUserWeaponUuid = weaponUuid
	user.DeckCharacters[slot] = dc
	log.Printf("[questflow] user %d: weapon %d given to its deck character", user.UserId, weaponId)
}

func ownedWeaponUuid(user *store.UserState, weaponId int32) string {
	for k, w := range user.Weapons {
		if w.WeaponId == weaponId {
			return k
		}
	}
	return ""
}
