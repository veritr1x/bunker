package masterdata

import (
	"os"
	"path/filepath"
	"testing"

	"lunar-tear/server/internal/masterdata/memorydb"
)

// loadBonusTestMaster opens the game data named by BUNKER_TEST_MASTER.
func loadBonusTestMaster(t *testing.T) {
	t.Helper()
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	path := filepath.Join(t.TempDir(), "master.bin.e")
	data, err := os.ReadFile(master)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := memorydb.Init(path); err != nil {
		t.Fatal(err)
	}
}

func TestImportantItemDropRatesOnTheGameData(t *testing.T) {
	loadBonusTestMaster(t)
	c, err := LoadImportantItemEffectCatalog()
	if err != nil {
		t.Fatal(err)
	}
	if len(c.DropRates) != 13 {
		t.Fatalf("%d drop rates, want 13", len(c.DropRates))
	}
	byItem := map[int32]ImportantItemDropRate{}
	for _, r := range c.DropRates {
		byItem[r.ImportantItemId] = r
	}
	if byItem[200019].RatePermil != 1000 {
		t.Errorf("Dungeon Drop Rate++: %+v", byItem[200019])
	}
	dark, ok := byItem[200021]
	if !ok || !c.ItemMatches(dark.ItemGroupId, 5, 100001) {
		t.Errorf("Dark Memory Drop Rate+ should target every drop: %+v", dark)
	}
	if c.ItemMatches(byItem[200007].ItemGroupId, 5, 999999) {
		t.Errorf("Wednesday Drop Rate+ targets an item outside its group")
	}
}

func TestQuestBonusExpOnTheGameData(t *testing.T) {
	loadBonusTestMaster(t)
	c, err := LoadQuestBonusCatalog()
	if err != nil {
		t.Fatal(err)
	}
	if e := c.ExpByEffect[105]; e.ExpType != 2 || e.BonusValuePermil != 500 {
		t.Fatalf("effect 105: %+v", e)
	}
}
