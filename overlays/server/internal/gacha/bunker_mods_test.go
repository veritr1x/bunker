package gacha

import (
	"os"
	"path/filepath"
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/mods"
	"lunar-tear/server/internal/store"
)

// Mods changes are in use at once in tests.
func init() { mods.Recheck = 0 }

func useMods(t *testing.T, body string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "mods.json")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	mods.SetPath(path)
	t.Cleanup(func() { mods.SetPath("") })
}

func fourStarCostume(id int32) masterdata.GachaPoolItem {
	return masterdata.GachaPoolItem{PossessionType: int32(model.PossessionTypeCostume), PossessionId: id, RarityType: model.RaritySSRare, CharacterId: id / 100}
}

func TestOwnedFourStarsAreSwappedForMissingOnes(t *testing.T) {
	user := &store.UserState{}
	user.EnsureMaps()
	user.Costumes["a"] = store.CostumeState{CostumeId: 101}
	bp := &masterdata.BannerPool{CostumesByRarity: map[int32][]masterdata.GachaPoolItem{
		int32(model.RaritySSRare): {fourStarCostume(101), fourStarCostume(102), fourStarCostume(103)},
	}}
	items := []DrawnItem{
		{PossessionType: int32(model.PossessionTypeCostume), PossessionId: 101, RarityType: model.RaritySSRare}, // owned
		{PossessionType: int32(model.PossessionTypeCostume), PossessionId: 102, RarityType: model.RaritySSRare}, // new
		{PossessionType: int32(model.PossessionTypeCostume), PossessionId: 102, RarityType: model.RaritySSRare}, // same summon
		{PossessionType: int32(model.PossessionTypeWeapon), PossessionId: 9, RarityType: model.RaritySRare},     // ★3: kept
	}
	swapDuplicateFourStars(user, items, bp, func(int) int { return 0 })
	got := []int32{items[0].PossessionId, items[1].PossessionId, items[2].PossessionId, items[3].PossessionId}
	// 101 is owned -> 102 (first missing); 102 then 102 again -> 103; the last one owned too, nothing left -> stays.
	want := []int32{102, 103, 102, 9}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("items = %v, want %v", got, want)
		}
	}
	if items[0].CharacterId != 1 {
		t.Fatalf("character not carried over: %d", items[0].CharacterId)
	}
}

func TestNoDuplicatesOnlyWithTheMod(t *testing.T) {
	useMods(t, `{}`)
	user := &store.UserState{}
	user.EnsureMaps()
	user.Costumes["a"] = store.CostumeState{CostumeId: 101}
	h := &GachaHandler{Pool: &masterdata.GachaCatalog{BannerPools: map[int32]*masterdata.BannerPool{1: {CostumesByRarity: map[int32][]masterdata.GachaPoolItem{
		int32(model.RaritySSRare): {fourStarCostume(101), fourStarCostume(102)}}}}}}
	items := []DrawnItem{{PossessionType: int32(model.PossessionTypeCostume), PossessionId: 101, RarityType: model.RaritySSRare}}
	h.applyNoDuplicateFourStar(user, store.GachaCatalogEntry{GachaId: 1, GachaLabelType: model.GachaLabelPremium}, items)
	if items[0].PossessionId != 101 {
		t.Fatal("swapped with the mod off")
	}
	useMods(t, `{"noDuplicateFourStar": true}`)
	h.applyNoDuplicateFourStar(user, store.GachaCatalogEntry{GachaId: 1, GachaLabelType: model.GachaLabelEvent}, items)
	if items[0].PossessionId != 101 {
		t.Fatal("swapped in an event summon")
	}
	h.applyNoDuplicateFourStar(user, store.GachaCatalogEntry{GachaId: 1, GachaLabelType: model.GachaLabelPremium}, items)
	if items[0].PossessionId != 102 {
		t.Fatalf("not swapped with the mod on: %d", items[0].PossessionId)
	}
}

func TestMedalsBecomeGemsInWholeHundreds(t *testing.T) {
	user := &store.UserState{}
	user.EnsureMaps()
	const medal, momPoint = int32(500), int32(9001)
	user.ConsumableItems[medal] = 250
	user.Gacha.BannerStates[7] = store.GachaBannerState{GachaId: 7, MedalCount: 250}
	h := &GachaHandler{Config: &masterdata.GameConfig{ConsumableItemIdForMomPoint: momPoint}}
	entry := store.GachaCatalogEntry{GachaId: 7, MedalConsumableItemId: medal}

	useMods(t, `{}`)
	h.applyPityRewards(user, entry, 1)
	if user.ConsumableItems[medal] != 250 || len(user.Gifts.NotReceived) != 0 {
		t.Fatal("medals traded with the mod off")
	}
	useMods(t, `{"pityRewards": true}`)
	h.applyPityRewards(user, entry, 1)
	if user.ConsumableItems[medal] != 50 || user.Gacha.BannerStates[7].MedalCount != 50 {
		t.Fatalf("medals left %d, banner %d, want 50", user.ConsumableItems[medal], user.Gacha.BannerStates[7].MedalCount)
	}
	var gems, mom int32
	for _, g := range user.Gifts.NotReceived {
		c := g.GiftCommon
		switch {
		case c.PossessionType == int32(model.PossessionTypePaidGem):
			gems += c.Count
		case c.PossessionType == int32(model.PossessionTypeConsumableItem) && c.PossessionId == momPoint:
			mom += c.Count
		}
	}
	if gems != 2000 || mom != 200 {
		t.Fatalf("gifts: %d paid gems, %d Mama Points; want 2000 and 200", gems, mom)
	}
}
