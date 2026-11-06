package lunarbase

import (
	"strings"
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func giftUser() (*store.UserState, *store.PossessionGranter) {
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	g := &store.PossessionGranter{Limits: store.PossessionLimits{Material: 99999, ConsumableItem: 99999, Weapon: 10}}
	return user, g
}

func TestGiftNeverExpiresAndReadsBunkerText(t *testing.T) {
	user, _ := giftUser()
	addBunkerGift(user, model.PossessionTypeMaterial, 100001, 5, 1000)
	if len(user.Gifts.NotReceived) != 1 {
		t.Fatalf("gifts: %+v", user.Gifts.NotReceived)
	}
	gift := user.Gifts.NotReceived[0]
	if gift.ExpirationDatetime != 0 || gift.GiftCommon.DescriptionGiftTextId != 90000 || gift.GiftCommon.Count != 5 || gift.UserGiftUuid == "" {
		t.Fatalf("gift: %+v", gift)
	}
	if user.Notifications.GiftNotReceiveCount != 1 {
		t.Fatalf("badge count %d", user.Notifications.GiftNotReceiveCount)
	}
}

func TestGiftRoomCountsHeldAndWaiting(t *testing.T) {
	user, g := giftUser()
	user.Materials[100001] = 99000
	addBunkerGift(user, model.PossessionTypeMaterial, 100001, 500, 1000)
	store.AddGift(user, model.PossessionTypeMaterial, 100001, 300, store.GiftTextOverflow, 1000) // not Bunker's
	if got := giftRoom(user, g, model.PossessionTypeMaterial, 100001); got != 499 {
		t.Fatalf("room %d, want 499", got)
	}
}

func TestSendGiftRefusesBeyondRoom(t *testing.T) {
	user, g := giftUser()
	user.Materials[100001] = 99500
	err := sendGift(user, g, model.PossessionTypeMaterial, 100001, 500, 1000)
	if err == nil || !strings.Contains(err.Error(), "499") {
		t.Fatalf("error %v, want one naming 499", err)
	}
	if len(user.Gifts.NotReceived) != 0 {
		t.Fatalf("a refused gift was written: %+v", user.Gifts.NotReceived)
	}
	if err := sendGift(user, g, model.PossessionTypeMaterial, 100001, 499, 1000); err != nil {
		t.Fatal(err)
	}
	if err := sendGift(user, g, model.PossessionTypeMaterial, 100001, 0, 1000); err == nil {
		t.Fatal("a gift of 0 was sent")
	}
}

func TestDebrisRoom(t *testing.T) {
	user, g := giftUser()
	if got := giftRoom(user, g, model.PossessionTypeThought, 7); got != 1 {
		t.Fatalf("free debris: room %d", got)
	}
	addBunkerGift(user, model.PossessionTypeThought, 7, 1, 1000)
	if got := giftRoom(user, g, model.PossessionTypeThought, 7); got != 0 {
		t.Fatalf("waiting debris: room %d", got)
	}
	store.GrantThought(user, 8, 1000)
	if got := giftRoom(user, g, model.PossessionTypeThought, 8); got != 0 {
		t.Fatalf("owned debris: room %d", got)
	}
}

func TestCharacterIsOnePerGift(t *testing.T) {
	user, g := giftUser()
	if err := sendGift(user, g, model.PossessionTypeCostume, 11011, 2, 1000); err == nil {
		t.Fatal("two copies of a character in one gift")
	}
	user.Costumes["c"] = store.CostumeState{CostumeId: 11011}
	if err := sendGift(user, g, model.PossessionTypeCostume, 11011, 1, 1000); err != nil {
		t.Fatalf("an owned character could not be sent: %v", err)
	}
}

func TestWeaponRoomCountsOwnedAndWaiting(t *testing.T) {
	user, g := giftUser()
	for _, k := range []string{"a", "b", "c"} {
		user.Weapons[k] = store.WeaponState{WeaponId: 101011}
	}
	addBunkerGift(user, model.PossessionTypeWeapon, 101021, 2, 1000)
	if got := giftRoom(user, g, model.PossessionTypeWeapon, 101031); got != 5 {
		t.Fatalf("room %d, want 10-3-2", got)
	}
}
