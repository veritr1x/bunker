package questflow

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

const rionWeapon = 101001

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

func TestFirstClearWeaponGiftStaysWhileTheQuestIsNotCleared(t *testing.T) {
	h := storyRewardHandler()
	u := testUser()
	u.Gifts.NotReceived = []store.NotReceivedGiftState{giftOf(store.GiftTextOverflow, rionWeapon)}
	if moved := h.ReturnFirstClearRewardsFromGiftBox(u, 1); moved != 0 || ownsWeapon(u, rionWeapon) {
		t.Fatalf("moved %d before the quest's first clear", moved)
	}
}
