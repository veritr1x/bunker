package service

import (
	"os"
	"path/filepath"
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/mods"
)

// Mods changes are in use at once in tests.
func init() { mods.Recheck = 0 }

func useServiceMods(t *testing.T, body string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "mods.json")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	mods.SetPath(path)
	t.Cleanup(func() { mods.SetPath("") })
}

func TestUnlimitedStockOnlyForRestockingItems(t *testing.T) {
	catalog := &masterdata.ShopCatalog{LimitedStockReset: map[int32]masterdata.ShopStockReset{
		1: {Type: masterdata.ShopAutoResetDaily, Period: 1},
		2: {Type: masterdata.ShopAutoResetDaily, Period: 7},
		3: {Type: masterdata.ShopAutoResetMonthly, Period: 1},
		4: {Type: masterdata.ShopAutoResetNone},
	}}
	item := func(stock int32) masterdata.EntityMShopItem {
		return masterdata.EntityMShopItem{ShopItemLimitedStockId: stock}
	}
	useServiceMods(t, `{}`)
	if modUnlimitedStock(catalog, item(1)) {
		t.Fatal("unlimited with the mod off")
	}
	useServiceMods(t, `{"shopUnlimited": true}`)
	for stock, want := range map[int32]bool{1: true, 2: true, 3: true, 4: false, 5: false, 0: false} {
		if got := modUnlimitedStock(catalog, item(stock)); got != want {
			t.Errorf("stock %d: unlimited = %v, want %v", stock, got, want)
		}
	}
}

func TestLostItemsGiveGemsOnlyWithTheMod(t *testing.T) {
	useServiceMods(t, `{"lostItemGems": true}`)
	for _, gimmick := range []model.GimmickType{model.GimmickTypeCageIntervalDropItem, model.GimmickTypeMapOnlyCageIntervalDrop} {
		if typ, id, n := lostItemDrop(gimmick); typ != model.PossessionTypeFreeGem || id != 0 || n < 100 {
			t.Fatalf("gimmick %d: %v %d %d", gimmick, typ, id, n)
		}
	}
	// Black birds keep their drops.
	if typ, _, _ := lostItemDrop(model.GimmickTypeCageTreasureHunt); typ == model.PossessionTypeFreeGem {
		t.Fatal("a black bird gave gems")
	}
}

func TestLostItemGemAmountsFollowTheirWeights(t *testing.T) {
	for roll, want := range map[int32]int32{0: 100, 24999: 100, 25000: 250, 34999: 250, 35000: 500, 35499: 500, 35500: 1000} {
		if got := pickLostItemGems(func(int32) int32 { return roll }); got != want {
			t.Errorf("roll %d: %d gems, want %d", roll, got, want)
		}
	}
}
