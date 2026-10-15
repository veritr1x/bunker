package masterdata

import (
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/internal/masterdata/memorydb"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// testGachaCatalog builds the summon catalog from the original master data (BUNKER_TEST_MASTER).
func testGachaCatalog(t *testing.T) []store.GachaCatalogEntry {
	t.Helper()
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	path := filepath.Join(t.TempDir(), "master.bin.e")
	in, err := os.Open(master)
	if err != nil {
		t.Fatal(err)
	}
	out, _ := os.Create(path)
	io.Copy(out, in)
	in.Close()
	out.Close()
	if err := memorydb.Init(path); err != nil {
		t.Fatal(err)
	}
	entries, _, err := LoadGachaCatalog()
	if err != nil {
		t.Fatal(err)
	}
	return entries
}

// Every multi-step summon the server offers costs, at each step, what the
// game's own step pages say (stepUpPrices), in the currency they name.
func TestStepUpPricesMatchTheStepPages(t *testing.T) {
	entries := testGachaCatalog(t)
	seen := 0
	for _, e := range entries {
		if e.GachaModeType != model.GachaModeStepup || !strings.HasPrefix(e.BannerAssetName, model.BannerPrefixStepUp) {
			continue
		}
		seen++
		group := stepUpGroup(e.BannerAssetName)
		want, ok := stepUpPrices[group]
		if !ok {
			t.Errorf("%s (gacha %d): no prices from its step pages", e.BannerAssetName, e.GachaId)
			continue
		}
		if len(e.PricePhases) != len(want) {
			t.Errorf("%s: %d steps, the pages have %d", e.BannerAssetName, len(e.PricePhases), len(want))
			continue
		}
		for i, p := range e.PricePhases {
			wantType := model.PriceTypeGem
			if want[i].Paid {
				wantType = model.PriceTypePaidGem
			}
			if p.Price != want[i].Gems || p.PriceType != wantType {
				t.Errorf("%s step %d: %d (type %d), the page says %d (type %d)", e.BannerAssetName, i+1, p.Price, p.PriceType, want[i].Gems, wantType)
			}
		}
	}
	if seen == 0 {
		t.Fatal("no multi-step summons in the catalog")
	}
}

// The examples from the pages: Resolute Dress (556) costs 3,000 / 1,500 any
// gems; Black Bird's step 1 (524) is free; New Year's Luck of the Draw (505)
// keeps its paid prices.
func TestStepUpPriceExamples(t *testing.T) {
	cases := map[int32][]stepUpPrice{
		556: {{3000, false}, {1500, false}, {3000, false}, {1500, false}, {3000, false}},
		524: {{0, false}, {1500, false}, {3000, false}, {3000, false}, {3000, false}},
		505: {{3000, true}, {0, false}, {2000, true}, {0, false}, {5000, true}},
	}
	for group, want := range cases {
		got := stepUpPrices[group]
		if len(got) != len(want) {
			t.Fatalf("group %d: %v", group, got)
		}
		for i := range want {
			if got[i] != want[i] {
				t.Errorf("group %d step %d: %v, want %v", group, i+1, got[i], want[i])
			}
		}
	}
}
