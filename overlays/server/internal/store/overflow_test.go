package store

import (
	"testing"

	"lunar-tear/server/internal/model"
)

func TestGrantFullSendsOverflowToGiftBox(t *testing.T) {
	g := testGranter()
	g.GachaMedalItemIds = map[int32]bool{8002: true}
	g.Limits.GachaMedal = 9999999
	user := SeedUserState(1, "u", 0, model.DefaultPlatform)
	user.Materials[100001] = 99990

	out := g.GrantFullAs(user, model.PossessionTypeMaterial, 100001, 25, 1000, GiftTextExchangeShopOverflow)
	if user.Materials[100001] != 99999 || len(out) != 1 || out[0].Count != 16 {
		t.Fatalf("held %d, overflow %+v", user.Materials[100001], out)
	}
	if len(user.Gifts.NotReceived) != 1 {
		t.Fatalf("gift box %+v", user.Gifts.NotReceived)
	}
	gift := user.Gifts.NotReceived[0]
	if gift.GiftCommon.PossessionId != 100001 || gift.GiftCommon.Count != 16 || gift.GiftCommon.DescriptionGiftTextId != GiftTextExchangeShopOverflow ||
		gift.ExpirationDatetime != 1000+GiftExpirationMillis || user.Notifications.GiftNotReceiveCount != 1 {
		t.Fatalf("gift %+v count %d", gift, user.Notifications.GiftNotReceiveCount)
	}

	// Weapons past the limit go to the gift box one by one; GrantFull uses text 11.
	g.GrantFull(user, model.PossessionTypeWeapon, 101001, 3, 1000)
	if len(user.Weapons) != 2 {
		t.Fatalf("weapons %d", len(user.Weapons))
	}
	last := user.Gifts.NotReceived[len(user.Gifts.NotReceived)-1]
	if last.GiftCommon.PossessionType != int32(model.PossessionTypeWeapon) || last.GiftCommon.Count != 1 || last.GiftCommon.DescriptionGiftTextId != GiftTextOverflow {
		t.Fatalf("weapon gift %+v", last)
	}
	if got := TakeGrantOverflow(user); len(got) != 2 || user.Ext.GrantOverflow != nil {
		t.Fatalf("overflow log %+v", got)
	}

	// Gacha medals use their own (higher) limit.
	user.ConsumableItems[8002] = 99999
	if out := g.GrantFullAs(user, model.PossessionTypeConsumableItem, 8002, 10, 1000, GiftTextSummons); len(out) != 0 || user.ConsumableItems[8002] != 100009 {
		t.Fatalf("gacha medal overflowed: %+v held %d", out, user.ConsumableItems[8002])
	}
}

func TestDuplicateExchangeOverflow(t *testing.T) {
	g := testGranter()
	user := SeedUserState(1, "u", 0, model.DefaultPlatform)
	g.GrantFull(user, model.PossessionTypeCostume, 21000, 1, 0)
	user.Materials[311053] = 99995
	if !g.WouldOverflow(user, model.PossessionTypeCostume, 21000, 1) {
		t.Fatal("owned costume whose exchange is over the limit should overflow")
	}
	out := g.GrantFullAs(user, model.PossessionTypeCostume, 21000, 1, 0, GiftTextOverflow)
	if user.Materials[311053] != 99999 || len(out) != 1 || out[0].Count != 6 ||
		user.Gifts.NotReceived[0].GiftCommon.DescriptionGiftTextId != GiftTextDuplicateCostume {
		t.Fatalf("material %d overflow %+v box %+v", user.Materials[311053], out, user.Gifts.NotReceived)
	}
	if g.WouldOverflow(user, model.PossessionTypeCostume, 99999, 1) {
		t.Fatal("a new costume never overflows")
	}
}

func TestGrantDebris(t *testing.T) {
	g := testGranter()
	user := SeedUserState(1, "u", 0, model.DefaultPlatform)
	g.GrantFull(user, model.PossessionTypeThought, 79100832, 1, 0)
	g.GrantFull(user, model.PossessionTypeThought, 79100832, 1, 0)
	n := 0
	for _, th := range user.Thoughts {
		if th.ThoughtId == 79100832 {
			n++
		}
	}
	if n != 1 {
		t.Fatalf("debris copies %d", n)
	}
}

// An overflow bigger than the limit is split so every gift can be claimed.
func TestOverflowGiftsFitTheLimit(t *testing.T) {
	g := testGranter()
	g.Limits.Material = 100
	user := SeedUserState(1, "u", 0, model.DefaultPlatform)
	user.Materials[100001] = 90
	g.GrantFullAs(user, model.PossessionTypeMaterial, 100001, 260, 1000, GiftTextExchangeShopOverflow)
	if user.Materials[100001] != 100 {
		t.Fatalf("held %d", user.Materials[100001])
	}
	total := int32(0)
	for _, gift := range user.Gifts.NotReceived {
		if gift.GiftCommon.Count > 100 {
			t.Fatalf("gift of %d is over the limit", gift.GiftCommon.Count)
		}
		total += gift.GiftCommon.Count
	}
	if total != 250 || len(user.Gifts.NotReceived) != 3 {
		t.Fatalf("%d gifts totalling %d, want 3 totalling 250", len(user.Gifts.NotReceived), total)
	}
}
