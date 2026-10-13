package gacha

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func chapterEntry() store.GachaCatalogEntry {
	return store.GachaCatalogEntry{
		GachaId:        200002,
		GachaLabelType: model.GachaLabelChapter,
		GachaModeType:  model.GachaModeBox,
		PricePhases: []store.GachaPricePhaseEntry{{
			PhaseId: 2000021, PriceType: model.PriceTypeConsumableItem, PriceId: 1008, Price: 1, DrawCount: 1,
		}},
	}
}

func testHandler() *GachaHandler {
	pool := &masterdata.GachaCatalog{Materials: []masterdata.GachaPoolItem{
		{PossessionType: int32(model.PossessionTypeMaterial), PossessionId: 100001, RarityType: model.RarityNormal},
	}}
	return NewGachaHandler(pool, &masterdata.GameConfig{PossessionCountLimitGachaMedal: 9999999}, &store.PossessionGranter{}, nil, nil)
}

func TestDrawFailsWithoutPayment(t *testing.T) {
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	before := store.CloneUserState(*user)
	if _, err := testHandler().HandleDraw(user, chapterEntry(), 2000021, 1); err == nil {
		t.Fatal("draw without the chapter ticket should fail")
	}
	if user.ConsumableItems[1008] != 0 || len(user.Materials) != len(before.Materials) || len(user.Gacha.BannerStates) != len(before.Gacha.BannerStates) {
		t.Fatalf("failed draw changed the user: materials %v banners %v", user.Materials, user.Gacha.BannerStates)
	}
}

func TestDrawPaysWithChapterTicket(t *testing.T) {
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	user.ConsumableItems[1008] = 3
	res, err := testHandler().HandleDraw(user, chapterEntry(), 2000021, 1)
	if err != nil {
		t.Fatal(err)
	}
	if user.ConsumableItems[1008] != 2 || len(res.Items) != 1 || user.Materials[100001] != 1 {
		t.Fatalf("tickets %d items %d material %d", user.ConsumableItems[1008], len(res.Items), user.Materials[100001])
	}
}

func TestMedalCountCap(t *testing.T) {
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	entry := chapterEntry()
	entry.GachaMedalId = 8002
	entry.PricePhases[0].Price = 0
	user.Gacha.BannerStates[entry.GachaId] = store.GachaBannerState{GachaId: entry.GachaId, MedalCount: 9999}
	if _, err := testHandler().HandleDraw(user, entry, 2000021, 1); err != nil {
		t.Fatal(err)
	}
	if got := user.Gacha.BannerStates[entry.GachaId].MedalCount; got != 10000 {
		t.Fatalf("medal count %d, want 10000 (limit is POSSESSION_COUNT_LIMIT_GACHA_MEDAL, not 9999)", got)
	}
}
