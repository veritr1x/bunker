package gacha

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func TestElementGuarantees(t *testing.T) {
	defer masterdata.SetElementsForTest(nil, nil)
	fireWeapon := masterdata.GachaPoolItem{PossessionType: int32(model.PossessionTypeWeapon), PossessionId: 2009, RarityType: model.RaritySSRare}
	masterdata.SetElementsForTest(map[int32]int32{2001: 1, 2009: 2}, map[int32]int32{1001: 2, 1002: 1}) // weapons; costumes (2 = fire)
	bp, pool := guaranteePool()
	bp.WeaponsByRarity[model.RaritySSRare] = append(bp.WeaponsByRarity[model.RaritySSRare], fireWeapon)
	items := []DrawnItem{drawn(ssrWeapon)} // a dark ★4 weapon
	applyGuarantee(items, bp, pool, masterdata.PhaseRule{Guar: "r4w:fire"}, 1)
	if items[0] != drawn(fireWeapon) {
		t.Fatalf("fire weapon guarantee gave %+v", items[0])
	}
	items = []DrawnItem{drawn(ssrCostumeB)} // a dark ★4 character
	applyGuarantee(items, bp, pool, masterdata.PhaseRule{Guar: "r4c:fire"}, 1)
	if items[0] != drawn(ssrCostumeA) {
		t.Fatalf("fire character guarantee gave %+v", items[0])
	}
	// Not an element: left to the rarity roll.
	items = []DrawnItem{drawn(ssrCostumeB)}
	applyGuarantee(items, bp, pool, masterdata.PhaseRule{Guar: "r4c:season1"}, 1)
	if items[0] != drawn(ssrCostumeB) {
		t.Fatalf("r4c:season1 replaced the slot: %+v", items[0])
	}
}

func ownerOf(ids ...int32) *store.UserState {
	u := &store.UserState{}
	u.EnsureMaps()
	for _, id := range ids {
		u.Costumes[string(rune('a'+id%26))+string(rune('0'+id%10))] = store.CostumeState{CostumeId: id}
	}
	return u
}

func TestUnownedCharacterGuarantee(t *testing.T) {
	bp, pool := guaranteePool()
	items := []DrawnItem{drawn(srWeapon), drawn(ssrCostumeA)}
	applyOwnedRules(ownerOf(1001), items, bp, pool, masterdata.PhaseRule{Guar: "r4c_unowned"}, 1)
	if items[1] != drawn(ssrCostumeB) {
		t.Fatalf("owned character kept: %+v", items[1])
	}
	// Owning every candidate: the slot stays as drawn.
	items = []DrawnItem{drawn(ssrCostumeA)}
	applyOwnedRules(ownerOf(1001, 1002), items, bp, pool, masterdata.PhaseRule{Guar: "set_unowned", Set: []int32{1001, 1002}}, 1)
	if items[0] != drawn(ssrCostumeA) {
		t.Fatalf("nothing unowned left, slot changed: %+v", items[0])
	}
}

func TestAwakenedFiveGrant(t *testing.T) {
	u := ownerOf(1001)
	for k, c := range u.Costumes {
		c.AwakenCount = 1
		u.Costumes[k] = c
	}
	awakenGranted(u, []DrawnItem{drawn(ssrCostumeA), drawn(srWeapon)}, masterdata.PhaseRule{Guar: "set_awakened5"})
	for _, c := range u.Costumes {
		if c.CostumeId == 1001 && c.AwakenCount != 5 {
			t.Fatalf("awakening %d", c.AwakenCount)
		}
	}
	awakenGranted(u, []DrawnItem{drawn(ssrCostumeA)}, masterdata.PhaseRule{Guar: "r4c"})
	// Other rules leave awakening alone (already 5 here; nothing lowered).
	for _, c := range u.Costumes {
		if c.AwakenCount != 5 {
			t.Fatalf("awakening changed by another rule: %d", c.AwakenCount)
		}
	}
}
