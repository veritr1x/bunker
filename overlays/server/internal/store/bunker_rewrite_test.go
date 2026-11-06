package store

import (
	"testing"

	"lunar-tear/server/internal/model"
)

// A gift that arrives as something else (Pod Programs > Mods) is checked
// against the limit of what arrives, not of the item it names.
func TestWouldOverflowChecksWhatArrives(t *testing.T) {
	g := testGranter()
	user := SeedUserState(1, "u", 0, model.DefaultPlatform)
	user.ConsumableItems[1003] = 99999 // the ticket stack is full
	if !g.WouldOverflow(user, model.PossessionTypeConsumableItem, 1003, 1) {
		t.Fatal("a full ticket stack did not overflow without the mod")
	}
	g.Rewrite = func(typ model.PossessionType, id, count int32) (model.PossessionType, int32, int32) {
		if typ == model.PossessionTypeConsumableItem && id == 1003 {
			return model.PossessionTypeMaterial, 100001, count * 10
		}
		return typ, id, count
	}
	if g.WouldOverflow(user, model.PossessionTypeConsumableItem, 1003, 1) {
		t.Fatal("a ticket that arrives as a material was refused for the ticket limit")
	}
	user.Materials[100001] = 99995
	if !g.WouldOverflow(user, model.PossessionTypeConsumableItem, 1003, 1) {
		t.Fatal("the material it arrives as is full, but it did not overflow")
	}
}
