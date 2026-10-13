package service

import (
	"testing"
	"time"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func gmt8(t *testing.T, s string) int64 {
	t.Helper()
	tm, err := time.ParseInLocation("2006-01-02 15:04", s, time.FixedZone("GMT-8", -8*60*60))
	if err != nil {
		t.Fatal(err)
	}
	return tm.UnixMilli()
}

func TestResetShopStockPerPeriod(t *testing.T) {
	catalog := &masterdata.ShopCatalog{
		Items: map[int32]masterdata.EntityMShopItem{
			1: {ShopItemId: 1, ShopItemLimitedStockId: 10}, // daily
			2: {ShopItemId: 2, ShopItemLimitedStockId: 20}, // 7-day
			3: {ShopItemId: 3, ShopItemLimitedStockId: 30}, // monthly
			4: {ShopItemId: 4, ShopItemLimitedStockId: 40}, // never
		},
		LimitedStockReset: map[int32]masterdata.ShopStockReset{
			10: {Type: masterdata.ShopAutoResetDaily, Period: 1},
			20: {Type: masterdata.ShopAutoResetDaily, Period: 7},
			30: {Type: masterdata.ShopAutoResetMonthly, Period: 1},
			40: {Type: masterdata.ShopAutoResetNone},
		},
	}
	// Bought Wednesday 2024-07-03 23:30 GMT-8.
	bought := gmt8(t, "2024-07-03 23:30")
	cases := []struct {
		now  string
		want [4]int32
	}{
		{"2024-07-03 23:59", [4]int32{1, 1, 1, 1}},
		{"2024-07-04 00:00", [4]int32{0, 1, 1, 1}}, // next GMT-8 day
		{"2024-07-08 00:00", [4]int32{0, 0, 1, 1}}, // next Monday
		{"2024-08-01 00:00", [4]int32{0, 0, 0, 1}}, // next month
	}
	for _, c := range cases {
		user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
		for id := int32(1); id <= 4; id++ {
			user.ShopItems[id] = store.UserShopItemState{ShopItemId: id, BoughtCount: 1, LatestBoughtCountChangedDatetime: bought}
		}
		now := gmt8(t, c.now)
		resetShopStock(catalog, user, now)
		for id := int32(1); id <= 4; id++ {
			if got := user.ShopItems[id].BoughtCount; got != c.want[id-1] {
				t.Errorf("%s item %d bought %d, want %d", c.now, id, got, c.want[id-1])
			}
		}
		if c.want[0] == 0 && user.ShopItems[1].LatestBoughtCountChangedDatetime != now {
			t.Errorf("%s reset time not recorded", c.now)
		}
	}
}

func TestShopOverflowGiftText(t *testing.T) {
	if shopOverflowGiftText(model.PriceTypeGem) != 31 || shopOverflowGiftText(model.PriceTypeConsumableItem) != 32 {
		t.Fatal("wrong MGiftText for shop overflow")
	}
}

// A gift at the cap stays in the box and makes no new gift.
func TestReceiveGiftAtCapNoLoop(t *testing.T) {
	g := &store.PossessionGranter{Limits: store.PossessionLimits{Weapon: 1, Material: 99999}}
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	g.GrantFull(user, model.PossessionTypeWeapon, 1, 1, 0)
	g.GrantFull(user, model.PossessionTypeWeapon, 2, 1, 0) // over the cap: to the gift box
	if len(user.Gifts.NotReceived) != 1 {
		t.Fatalf("gift box %+v", user.Gifts.NotReceived)
	}
	id := user.Gifts.NotReceived[0].UserGiftUuid
	for range 3 {
		received, _, overflow := receiveGifts(user, g, []string{id}, 100, 1000)
		if len(received) != 0 || len(overflow) != 1 || len(user.Gifts.NotReceived) != 1 || len(user.Weapons) != 1 {
			t.Fatalf("received %v overflow %v box %d weapons %d", received, overflow, len(user.Gifts.NotReceived), len(user.Weapons))
		}
	}
}

func TestReleaseCharacterViewerFieldsOnlyNew(t *testing.T) {
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	if got := releaseCharacterViewerFields(user, []int32{1, 2}, 100); len(got) != 2 {
		t.Fatalf("first visit %v", got)
	}
	if got := releaseCharacterViewerFields(user, []int32{1, 2}, 200); len(got) != 0 {
		t.Fatalf("repeat visit %v", got)
	}
	if got := releaseCharacterViewerFields(user, []int32{1, 2, 3}, 300); len(got) != 1 || got[0] != 3 {
		t.Fatalf("new field %v", got)
	}
	if user.Ext.CharacterViewerFields[1] != 100 || user.Ext.CharacterViewerFields[3] != 300 {
		t.Fatalf("release times %v", user.Ext.CharacterViewerFields)
	}
}

func TestMamaBannerPicksUnlockedChapter(t *testing.T) {
	chapter := func(id, quest int32) store.GachaCatalogEntry {
		return store.GachaCatalogEntry{GachaId: id, GachaLabelType: model.GachaLabelChapter, IsUserGachaUnlock: true,
			UnlockConditionType: model.GachaUnlockMainQuestClear, UnlockConditionValue: quest}
	}
	catalog := []store.GachaCatalogEntry{chapter(1, 0), chapter(2, 20), chapter(3, 30)}
	catalog[0].UnlockConditionType = 0
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	if b := mamaBanner(catalog, user, 0).LatestChapterGacha; b == nil || b.GachaId != 1 {
		t.Fatalf("banner %v, want 1", b)
	}
	user.Quests[20] = store.UserQuestState{QuestId: 20, QuestStateType: model.UserQuestStateTypeCleared, ClearCount: 1}
	if b := mamaBanner(catalog, user, 0).LatestChapterGacha; b == nil || b.GachaId != 2 {
		t.Fatalf("banner %v, want 2", b)
	}
}
