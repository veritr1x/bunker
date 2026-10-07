package gacha

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
)

func total(tiers []RateTier) (all, four int) {
	for _, t := range tiers {
		all += t.Weight
		if t.RarityType >= model.RaritySSRare {
			four += t.Weight
		}
	}
	return
}

func TestDefaultRatesMatchLunarTear(t *testing.T) {
	got := DefaultRates.Tiers()
	for i, want := range premiumRates {
		if got[i].Weight != want.Weight*10 || got[i].PossessionType != want.PossessionType || got[i].RarityType != want.RarityType {
			t.Fatalf("tier %d: got %+v, want %+v (x10)", i, got[i], want)
		}
	}
}

func TestRatesFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "gacha_rates.json")
	SetRatesPath(path)
	defer SetRatesPath("")
	if Rates() != DefaultRates {
		t.Fatal("missing file should give the defaults")
	}
	os.WriteFile(path, []byte(`{"fourStarPercent":20,"threeStarPercent":30,"fourStarCostumeShare":50,"threeStarCostumeShare":50,"featuredPercent":100,"stepUpBoost":false,"multiMinRarity":4}`), 0600)
	c := Rates()
	all, four := total(c.Tiers())
	if all != 100000 || four != 20000 || c.GuaranteedRarity() != model.RaritySSRare || c.StepUpBoost {
		t.Fatalf("custom rates not read: %+v total=%d four=%d", c, all, four)
	}
	// An invalid file falls back to the defaults.
	time.Sleep(10 * time.Millisecond)
	os.WriteFile(path, []byte(`{"fourStarPercent":90,"threeStarPercent":30}`), 0600)
	os.Chtimes(path, time.Now().Add(time.Second), time.Now().Add(time.Second))
	if Rates() != DefaultRates {
		t.Fatal("invalid file should give the defaults")
	}
	// 100% 4★: no other tier is drawn.
	only := RateConfig{FourStarPercent: 100, FeaturedPercent: 35, MultiMinRarity: 3}
	if err := only.Validate(); err != nil {
		t.Fatal(err)
	}
	if tiers := only.Tiers(); len(tiers) != 1 || tiers[0].RarityType != model.RaritySSRare {
		t.Fatalf("100%% 4★ weapons: %+v", tiers)
	}
}

func testPool() *masterdata.BannerPool {
	item := func(t model.PossessionType, id int32, r model.RarityType) masterdata.GachaPoolItem {
		return masterdata.GachaPoolItem{PossessionType: int32(t), PossessionId: id, RarityType: r}
	}
	bp := &masterdata.BannerPool{CostumesByRarity: map[int32][]masterdata.GachaPoolItem{}, WeaponsByRarity: map[int32][]masterdata.GachaPoolItem{}}
	for _, r := range []model.RarityType{model.RarityRare, model.RaritySRare, model.RaritySSRare} {
		bp.CostumesByRarity[r] = []masterdata.GachaPoolItem{item(model.PossessionTypeCostume, 1000+r, r)}
		bp.WeaponsByRarity[r] = []masterdata.GachaPoolItem{item(model.PossessionTypeWeapon, 2000+r, r)}
	}
	bp.Featured = []masterdata.GachaPoolItem{item(model.PossessionTypeCostume, 9999, model.RaritySSRare)}
	return bp
}

func TestDrawsFollowTheRates(t *testing.T) {
	path := filepath.Join(t.TempDir(), "gacha_rates.json")
	SetRatesPath(path)
	defer SetRatesPath("")
	const n = 20000
	share := func() (four, featured float64) {
		var f, ft int
		for _, it := range DrawPremium(testPool(), n, 0, 0, 1) {
			if it.RarityType == model.RaritySSRare {
				f++
				if it.PossessionId == 9999 {
					ft++
				}
			}
		}
		return float64(f) / n * 100, float64(ft) / n * 100
	}
	if four, _ := share(); four < 4 || four > 6 {
		t.Fatalf("default 4★ share %.2f%%, want about 5%%", four)
	}
	// 30% 4★, all costumes, every costume draw featured: 30% featured.
	os.WriteFile(path, []byte(`{"fourStarPercent":30,"threeStarPercent":20,"fourStarCostumeShare":100,"threeStarCostumeShare":50,"featuredPercent":100,"stepUpBoost":true,"multiMinRarity":4}`), 0600)
	if four, featured := share(); four < 28 || four > 32 || featured < 28 || featured > 32 {
		t.Fatalf("custom: 4★ %.2f%%, featured %.2f%%; want about 30%% each", four, featured)
	}
	// The 10-draw guarantee follows multiMinRarity.
	for i := 0; i < 200; i++ {
		items := DrawPremium(testPool(), 10, Rates().GuaranteedRarity(), 1, 1)
		if items[9].RarityType != model.RaritySSRare {
			t.Fatalf("guaranteed slot drew %d", items[9].RarityType)
		}
	}
}
