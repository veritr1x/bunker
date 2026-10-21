package gacha

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
)

var (
	ssrCostumeA = masterdata.GachaPoolItem{PossessionType: int32(model.PossessionTypeCostume), PossessionId: 1001, RarityType: model.RaritySSRare, CharacterId: 1}
	ssrCostumeB = masterdata.GachaPoolItem{PossessionType: int32(model.PossessionTypeCostume), PossessionId: 1002, RarityType: model.RaritySSRare, CharacterId: 2}
	ssrWeapon   = masterdata.GachaPoolItem{PossessionType: int32(model.PossessionTypeWeapon), PossessionId: 2001, RarityType: model.RaritySSRare}
	srWeapon    = masterdata.GachaPoolItem{PossessionType: int32(model.PossessionTypeWeapon), PossessionId: 2101, RarityType: model.RaritySRare}
)

func guaranteePool() (*masterdata.BannerPool, *masterdata.GachaCatalog) {
	bp := &masterdata.BannerPool{
		CostumesByRarity: map[int32][]masterdata.GachaPoolItem{model.RaritySSRare: {ssrCostumeA, ssrCostumeB}},
		WeaponsByRarity:  map[int32][]masterdata.GachaPoolItem{model.RaritySSRare: {ssrWeapon}, model.RaritySRare: {srWeapon}},
		Featured:         []masterdata.GachaPoolItem{ssrCostumeB},
	}
	pool := &masterdata.GachaCatalog{CostumeById: map[int32]masterdata.GachaPoolItem{1001: ssrCostumeA, 1002: ssrCostumeB}}
	return bp, pool
}

func drawn(i masterdata.GachaPoolItem) DrawnItem {
	return DrawnItem{PossessionType: i.PossessionType, PossessionId: i.PossessionId, RarityType: i.RarityType, CharacterId: i.CharacterId}
}

func lastAfter(t *testing.T, rule masterdata.PhaseRule, last masterdata.GachaPoolItem) DrawnItem {
	t.Helper()
	bp, pool := guaranteePool()
	items := []DrawnItem{drawn(srWeapon), drawn(last)}
	applyGuarantee(items, bp, pool, rule, 1)
	if items[0] != drawn(srWeapon) {
		t.Fatalf("a slot before the guaranteed one changed: %+v", items[0])
	}
	return items[1]
}

func TestGuaranteedFeaturedCharacter(t *testing.T) {
	if got := lastAfter(t, masterdata.PhaseRule{Guar: "set10:feat"}, srWeapon); got != drawn(ssrCostumeB) {
		t.Fatalf("featured guarantee gave %+v", got)
	}
	if got := lastAfter(t, masterdata.PhaseRule{Guar: "r4c_feat"}, ssrCostumeA); got != drawn(ssrCostumeB) {
		t.Fatalf("a ★4 that isn't featured was kept: %+v", got)
	}
	if got := lastAfter(t, masterdata.PhaseRule{Guar: "set10:feat"}, ssrCostumeB); got != drawn(ssrCostumeB) {
		t.Fatalf("a featured draw was replaced: %+v", got)
	}
}

func TestGuaranteedListedSet(t *testing.T) {
	if got := lastAfter(t, masterdata.PhaseRule{Guar: "set10", Set: []int32{1001}}, ssrCostumeB); got != drawn(ssrCostumeA) {
		t.Fatalf("listed set gave %+v", got)
	}
}

func TestGuaranteedWeaponAndCharacter(t *testing.T) {
	if got := lastAfter(t, masterdata.PhaseRule{Guar: "r4w"}, ssrCostumeA); got != drawn(ssrWeapon) {
		t.Fatalf("★4 weapon guarantee gave %+v", got)
	}
	if got := lastAfter(t, masterdata.PhaseRule{Guar: "r4c"}, ssrWeapon); got.PossessionType != int32(model.PossessionTypeCostume) || got.RarityType != model.RaritySSRare {
		t.Fatalf("★4 character guarantee gave %+v", got)
	}
	// A set the archive doesn't list (resonant characters) gives a ★4 character.
	if got := lastAfter(t, masterdata.PhaseRule{Guar: "set10:resonant"}, srWeapon); got.PossessionType != int32(model.PossessionTypeCostume) || got.RarityType != model.RaritySSRare {
		t.Fatalf("unlisted set gave %+v", got)
	}
}

func TestPlainGuaranteesAreLeftToTheRarityRoll(t *testing.T) {
	// r3w/r4 are handled by the slot's minimum rarity; the slot isn't replaced.
	for _, g := range []string{"r3w", "r4", ""} {
		if got := lastAfter(t, masterdata.PhaseRule{Guar: g}, srWeapon); got != drawn(srWeapon) {
			t.Fatalf("%q replaced the slot: %+v", g, got)
		}
	}
}

func TestRuleRateReplacesTheStepBoost(t *testing.T) {
	if got := ruleRate(masterdata.PhaseRule{Rate: 2}, true, 1.5); got != 2 {
		t.Fatalf("rule rate: %v", got)
	}
	// A step the notice gives no rate-up for draws at the normal rate.
	if got := ruleRate(masterdata.PhaseRule{}, true, 1.5); got != 1 {
		t.Fatalf("no rate-up: %v", got)
	}
	if got := ruleRate(masterdata.PhaseRule{}, false, 1.5); got != 1.5 {
		t.Fatalf("summon without rules: %v", got)
	}
}

// Paid-only twins: every ★4 that appears is a featured one ("all ★★★★
// weapons that appear are guaranteed to be featured weapons").
func TestEveryFourStarIsFeatured(t *testing.T) {
	bp, _ := guaranteePool()
	featuredWeapon := masterdata.GachaPoolItem{PossessionType: int32(model.PossessionTypeWeapon), PossessionId: 2002, RarityType: model.RaritySSRare}
	bp.Featured = append(bp.Featured, featuredWeapon)
	items := []DrawnItem{drawn(ssrCostumeA), drawn(srWeapon), drawn(ssrWeapon), drawn(ssrCostumeB)}
	featureEveryFourStar(items, bp)
	want := []DrawnItem{drawn(ssrCostumeB), drawn(srWeapon), drawn(featuredWeapon), drawn(ssrCostumeB)}
	for i := range want {
		if items[i] != want[i] {
			t.Fatalf("slot %d: %+v, want %+v", i, items[i], want[i])
		}
	}
}

func TestEveryFourStarWithoutFeaturedWeaponsKeepsWeapons(t *testing.T) {
	bp, _ := guaranteePool() // featured: one costume, no weapons
	items := []DrawnItem{drawn(ssrWeapon)}
	featureEveryFourStar(items, bp)
	if items[0] != drawn(ssrWeapon) {
		t.Fatalf("a ★4 weapon was replaced with nothing to replace it by: %+v", items[0])
	}
}
