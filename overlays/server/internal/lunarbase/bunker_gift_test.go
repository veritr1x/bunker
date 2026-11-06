package lunarbase

import (
	"strings"
	"testing"
	"time"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
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
	// The game's Gift Box shows nothing at all when a gift has no deadline, so
	// "never expires" is 2099-12-31 23:59:59 UTC.
	if gift.ExpirationDatetime != 4102444799000 || gift.GiftCommon.DescriptionGiftTextId != 90000 || gift.GiftCommon.Count != 5 || gift.UserGiftUuid == "" {
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

// The shim's granter has no possession limits of its own (the server adds
// them in runtime.wireGranter): a gift's room takes them from the game data.
func TestGiftLimitsComeFromTheGameData(t *testing.T) {
	g := &store.PossessionGranter{}
	cfg := &masterdata.GameConfig{PossessionCountLimitConsumableItem: 99999, PossessionCountLimitMaterial: 99999, PossessionCountLimitMoney: 999999999,
		PossessionCountLimitGachaMedal: 9999999, PossessionCountLimitWeapon: 2000, PossessionCountLimitParts: 999, PossessionCountLimitImportantItem: 999,
		ConsumableItemIdForGold: 1}
	withLimits(g, cfg, []masterdata.EntityMConsumableItem{{ConsumableItemId: 8001, ConsumableItemType: 120}, {ConsumableItemId: 1002, ConsumableItemType: 200}})
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	user.ConsumableItems[1002] = 10
	for _, c := range []struct {
		t    model.PossessionType
		id   int32
		want int64
	}{{model.PossessionTypeConsumableItem, 1002, 99989}, {model.PossessionTypeConsumableItem, 8001, 9999999},
		{model.PossessionTypeConsumableItem, 1, 999999999}, {model.PossessionTypeMaterial, 100001, 99999}} {
		if got := giftRoom(user, g, c.t, c.id); got != c.want {
			t.Errorf("%d %d: room %d, want %d", c.t, c.id, got, c.want)
		}
	}
}

// With the server running, the room comes from the live server's granter:
// no master data is loaded (the server's own is shared), and the mods'
// conversions count, as they do when the gift is claimed.
func TestGiftRoomUsesTheLiveGranter(t *testing.T) {
	user, g := giftUser()
	g.Limits.Money = 1000
	g.GoldConsumableItemId = 1
	user.ConsumableItems[1] = 400
	g.Rewrite = func(pt model.PossessionType, id, n int32) (model.PossessionType, int32, int32) {
		if pt == model.PossessionTypeConsumableItem && id == 3001 {
			return model.PossessionTypeConsumableItem, 1, n * 120 // a stamina item arrives as 120 gold
		}
		return pt, id, n
	}
	saved := LiveGranter
	t.Cleanup(func() { LiveGranter = saved })
	LiveGranter = func() *store.PossessionGranter { return g }
	got, err := giftGranter(&request{}) // no master_data_path: nothing loaded
	if err != nil || got != g {
		t.Fatalf("granter %p, %v; want the live one", got, err)
	}
	// 600 gold of room left: 5 stamina items (5×120), not the item's own cap.
	if room := giftRoom(user, g, model.PossessionTypeConsumableItem, 3001); room != 5 {
		t.Fatalf("room %d, want 5", room)
	}
}

// A gift's grant time is the game's clock (the Original calendar's), like the
// server's own gifts, not the device's.
func TestGiftTimeIsTheGameClock(t *testing.T) {
	saved := gametime.CurrentCalendar()
	t.Cleanup(func() { gametime.SetCalendar(saved) })
	year := int64(365 * 24 * 60 * 60 * 1000)
	gametime.SetCalendar(&gametime.Calendar{Version: 1, Loop: 1, LoopStart: gametime.Launch, JumpMillis: year, Speed: 1})
	if d := giftNow() - time.Now().UnixMilli(); d < year-60_000 || d > year+60_000 {
		t.Fatalf("gift time is %d ms from the device's, want the calendar's year ahead", d)
	}
}
