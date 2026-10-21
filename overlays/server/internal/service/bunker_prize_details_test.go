package service

import (
	"net/http/httptest"
	"strings"
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

func dreamPrizes() []masterdata.Prize {
	return []masterdata.Prize{
		{Name: "Gems", Type: 12, Qty: 300000, Stock: 1},
		{Name: "Gems", Type: 12, Qty: 100, Stock: 1000},
		{Name: "Karma Stone", Type: 5, Id: 315001, Qty: 10, Weight: 1000},
	}
}

func TestPrizeSectionShowsWhatIsLeft(t *testing.T) {
	users := newMemUsers()
	users.user.EnsureMaps()
	users.user.Gacha.BannerStates[200001] = store.GachaBannerState{GachaId: 200001, BoxDrewCounts: map[int32]int32{1: 250}}
	SetWebUsers(users)
	defer SetWebUsers(nil)
	r := httptest.NewRequest("GET", "/web/en/gacha-details?gachaId=200001&userId=1&sessionKey=x", nil)
	page := prizeSectionHTML(r, 200001, dreamPrizes())
	for _, want := range []string{"PRIZES", "Gems ×300,000", "1 of 1 left", "Gems ×100", "750 of 1,000 left", "Karma Stone ×10", "unlimited"} {
		if !strings.Contains(page, want) {
			t.Fatalf("missing %q in:\n%s", want, page)
		}
	}
}

func TestPrizeSectionWithoutThePlayer(t *testing.T) {
	SetWebUsers(nil)
	r := httptest.NewRequest("GET", "/web/en/gacha-details?gachaId=200001", nil)
	page := prizeSectionHTML(r, 200001, dreamPrizes())
	// The stock as the notice gave it, without what's left.
	if !strings.Contains(page, "Gems ×300,000") || !strings.Contains(page, "stock 1") || strings.Contains(page, "of 1 left") {
		t.Fatalf("page without a player:\n%s", page)
	}
}

// The summon screen shows the limited prizes' stock (notice 1618: "remaining
// stock of each prize appears on both the summons screen and details window"):
// the box panel's lines, first four, with what has been drawn.
func TestPrizeBoxLinesShowTheStockLeft(t *testing.T) {
	prizes := append(dreamPrizes(), masterdata.Prize{Name: "Gems", Type: 12, Qty: 28, Stock: 9}, masterdata.Prize{Name: "Gems", Type: 12, Qty: 2, Stock: 9})
	bs := store.GachaBannerState{BoxDrewCounts: map[int32]int32{1: 250}}
	lines := prizeBoxLines(prizes, bs)
	if len(lines) != 4 {
		t.Fatalf("%d lines, want the 4 limited prizes", len(lines))
	}
	first, second := lines[0], lines[1]
	if first.GachaItem.PossessionType != 12 || first.GachaItem.Count != 300000 || first.MaxDrawableCount != 1 || first.DrewCount != 0 || !first.IsTarget {
		t.Fatalf("top prize line: %+v", first)
	}
	if second.GachaItem.Count != 100 || second.MaxDrawableCount != 1000 || second.DrewCount != 250 {
		t.Fatalf("second prize line: %+v", second)
	}
	if lines[2].GachaItem.Count != 28 || lines[3].GachaItem.Count != 2 {
		t.Fatalf("unlimited prizes shown, or limited ones skipped: %+v %+v", lines[2], lines[3])
	}
}
