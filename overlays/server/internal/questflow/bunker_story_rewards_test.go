package questflow

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

const (
	rionWeapon  = 101001
	rionCostume = 10100
)

// A handler whose testQuest gives Rion's weapon on its first clear, with room for one weapon.
func storyRewardHandler() *QuestHandler {
	h := testHandler()
	h.QuestById[testQuest] = masterdata.EntityMQuest{QuestId: testQuest, QuestFirstClearRewardGroupId: 9}
	h.FirstClearRewardsByGroupId = map[int32][]masterdata.EntityMQuestFirstClearRewardGroup{
		9: {{QuestFirstClearRewardGroupId: 9, PossessionType: int32(model.PossessionTypeWeapon), PossessionId: rionWeapon, Count: 1}},
	}
	h.Granter.Limits.Weapon = 1
	return h
}

func ownsWeapon(u *store.UserState, weaponId int32) bool {
	for _, w := range u.Weapons {
		if w.WeaponId == weaponId {
			return true
		}
	}
	return false
}

func giftOf(text, weaponId int32) store.NotReceivedGiftState {
	return store.NotReceivedGiftState{UserGiftUuid: "g", GiftCommon: store.GiftCommonState{
		PossessionType: int32(model.PossessionTypeWeapon), PossessionId: weaponId, Count: 1, DescriptionGiftTextId: text}}
}

// A full weapon storage (from early summons) sent Rion's weapon to the gift box,
// and the chapter 2 loadout tutorial then could not be finished.
func TestFirstClearWeaponArrivesPastTheWeaponLimit(t *testing.T) {
	h := storyRewardHandler()
	u := testUser() // already holds one weapon: the storage is full
	h.applyFirstClearItemRewards(u, testQuest, 1)
	if !ownsWeapon(u, rionWeapon) {
		t.Fatal("the first-clear weapon went to the gift box")
	}
	if len(u.Gifts.NotReceived) != 0 {
		t.Fatalf("%d gifts, want none", len(u.Gifts.NotReceived))
	}
}

func TestOverflowedFirstClearWeaponComesBackFromTheGiftBox(t *testing.T) {
	h := storyRewardHandler()
	u := testUser()
	u.Quests[testQuest] = store.UserQuestState{QuestId: testQuest, QuestStateType: model.UserQuestStateTypeCleared, IsRewardGranted: true}
	u.Gifts.NotReceived = []store.NotReceivedGiftState{
		giftOf(store.GiftTextOverflow, rionWeapon),
		giftOf(1, rionWeapon),                      // a summon's overflow stays a gift
		giftOf(store.GiftTextOverflow, testWeapon), // not a first-clear reward
	}
	if moved := h.ReturnFirstClearRewardsFromGiftBox(u, 1); moved != 1 {
		t.Fatalf("moved %d, want 1", moved)
	}
	if !ownsWeapon(u, rionWeapon) {
		t.Fatal("Rion's weapon is still not in the inventory")
	}
	if len(u.Gifts.NotReceived) != 2 || u.Notifications.GiftNotReceiveCount != 2 {
		t.Fatalf("%d gifts (count %d), want the other 2", len(u.Gifts.NotReceived), u.Notifications.GiftNotReceiveCount)
	}
	// Run again (next game start): nothing more moves.
	if moved := h.ReturnFirstClearRewardsFromGiftBox(u, 2); moved != 0 {
		t.Fatalf("moved %d on the second start", moved)
	}
}

// The loadout tutorial's first step built deck 1 while Rion's weapon was in the
// gift box, so Rion has no main weapon there and the tutorial's Select did
// nothing even once the weapon was back.
func TestReturnedRionWeaponGoesToRionInTheDeck(t *testing.T) {
	h := storyRewardHandler()
	u := testUser()
	u.Quests[testQuest] = store.UserQuestState{QuestId: testQuest, QuestStateType: model.UserQuestStateTypeCleared, IsRewardGranted: true}
	u.Costumes["rion"] = store.CostumeState{UserCostumeUuid: "rion", CostumeId: rionCostume}
	u.DeckCharacters["rd"] = store.DeckCharacterState{UserDeckCharacterUuid: "rd", UserCostumeUuid: "rion"}
	u.Gifts.NotReceived = []store.NotReceivedGiftState{giftOf(store.GiftTextOverflow, rionWeapon)}
	h.ReturnFirstClearRewardsFromGiftBox(u, 1)
	w, ok := u.Weapons[u.DeckCharacters["rd"].MainUserWeaponUuid]
	if !ok || w.WeaponId != rionWeapon {
		t.Fatalf("Rion's main weapon is %q, want Rion's weapon", u.DeckCharacters["rd"].MainUserWeaponUuid)
	}
	if u.DeckCharacters["d1"].MainUserWeaponUuid != "w1" {
		t.Fatal("a deck character that had a weapon was changed")
	}
}

// The weapon is back (its gift claimed, or moved by an earlier start) but Rion
// still has no main weapon.
func TestOwnedRionWeaponGoesToRionInTheDeck(t *testing.T) {
	h := storyRewardHandler()
	u := testUser()
	u.Weapons["rw"] = store.WeaponState{UserWeaponUuid: "rw", WeaponId: rionWeapon}
	u.Costumes["rion"] = store.CostumeState{UserCostumeUuid: "rion", CostumeId: rionCostume}
	u.DeckCharacters["rd"] = store.DeckCharacterState{UserDeckCharacterUuid: "rd", UserCostumeUuid: "rion"}
	h.ReturnFirstClearRewardsFromGiftBox(u, 1)
	if got := u.DeckCharacters["rd"].MainUserWeaponUuid; got != "rw" {
		t.Fatalf("Rion's main weapon is %q, want rw", got)
	}
}

func TestFirstClearWeaponGiftStaysWhileTheQuestIsNotCleared(t *testing.T) {
	h := storyRewardHandler()
	u := testUser()
	u.Gifts.NotReceived = []store.NotReceivedGiftState{giftOf(store.GiftTextOverflow, rionWeapon)}
	if moved := h.ReturnFirstClearRewardsFromGiftBox(u, 1); moved != 0 || ownsWeapon(u, rionWeapon) {
		t.Fatalf("moved %d before the quest's first clear", moved)
	}
}

// The overflow gift expired (30 days) before the player updated: Rion's slot
// is empty and the weapon is nowhere, so it is given again.
func TestLostRionWeaponIsGivenAgainForTheEmptySlot(t *testing.T) {
	h := storyRewardHandler()
	u := testUser()
	u.Costumes["rion"] = store.CostumeState{UserCostumeUuid: "rion", CostumeId: rionCostume}
	u.DeckCharacters["rd"] = store.DeckCharacterState{UserDeckCharacterUuid: "rd", UserCostumeUuid: "rion"}
	h.RepairOnGameStart(u, 1)
	w, ok := u.Weapons[u.DeckCharacters["rd"].MainUserWeaponUuid]
	if !ok || w.WeaponId != rionWeapon {
		t.Fatal("Rion's weapon was not given again")
	}
	h.RepairOnGameStart(u, 2)
	n := 0
	for _, w := range u.Weapons {
		if w.WeaponId == rionWeapon {
			n++
		}
	}
	if n != 1 {
		t.Fatalf("%d copies after the second start, want 1", n)
	}
}

// A player who gave Rion another weapon and sold Rion's gets nothing back.
func TestRionWeaponNotGivenAgainWhenRionHasAWeapon(t *testing.T) {
	h := storyRewardHandler()
	u := testUser()
	u.Costumes["rion"] = store.CostumeState{UserCostumeUuid: "rion", CostumeId: rionCostume}
	u.DeckCharacters["rd"] = store.DeckCharacterState{UserDeckCharacterUuid: "rd", UserCostumeUuid: "rion", MainUserWeaponUuid: "w1"}
	h.RepairOnGameStart(u, 1)
	if ownsWeapon(u, rionWeapon) {
		t.Fatal("Rion's weapon given again although Rion holds a weapon")
	}
}
