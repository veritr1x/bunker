package runtime

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

func TestItemsArriveAsOthersOnlyWithTheirMods(t *testing.T) {
	path := filepath.Join(t.TempDir(), "mods.json")
	mods.SetPath(path)
	t.Cleanup(func() { mods.SetPath("") })
	items := []masterdata.EntityMConsumableItem{{ConsumableItemId: 3002}, {ConsumableItemId: 1002}, {ConsumableItemId: 1210}, {ConsumableItemId: 7}}
	rewrite := modRewrite(items, 1)
	check := func(id, count int32, wantType model.PossessionType, wantId, wantCount int32) {
		t.Helper()
		typ, gotId, n := rewrite(model.PossessionTypeConsumableItem, id, count)
		if typ != wantType || gotId != wantId || n != wantCount {
			t.Fatalf("item %d ×%d -> %v %d ×%d, want %v %d ×%d", id, count, typ, gotId, n, wantType, wantId, wantCount)
		}
	}
	// No mods: everything arrives as it is.
	check(3002, 2, model.PossessionTypeConsumableItem, 3002, 2)
	check(1002, 1, model.PossessionTypeConsumableItem, 1002, 1)

	if err := os.WriteFile(path, []byte(`{"staminaItemsToGold": true, "ticketsToGems": true}`), 0o600); err != nil {
		t.Fatal(err)
	}
	check(3002, 2, model.PossessionTypeConsumableItem, 1, 480)
	check(1002, 3, model.PossessionTypeFreeGem, 0, 900)
	check(1210, 1, model.PossessionTypeFreeGem, 0, 9000)
	check(7, 5, model.PossessionTypeConsumableItem, 7, 5)
	// 3001 is not in this master data: left alone.
	check(3001, 1, model.PossessionTypeConsumableItem, 3001, 1)
	if typ, _, _ := rewrite(model.PossessionTypeMaterial, 3002, 1); typ != model.PossessionTypeMaterial {
		t.Fatal("a material was converted")
	}
}
