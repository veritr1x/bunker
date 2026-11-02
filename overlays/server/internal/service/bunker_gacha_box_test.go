package service

import (
	"io"
	"net/http/httptest"
	"strings"
	"testing"

	"lunar-tear/server/internal/store"
)

// boxPage is the page the game opens from a box summon's "i" button.
func boxPage(t *testing.T, url string) string {
	t.Helper()
	s := &OctoHTTPServer{}
	rec := httptest.NewRecorder()
	r := httptest.NewRequest("GET", url, nil)
	s.handleWebAPI(rec, r, r.URL.Path)
	page, _ := io.ReadAll(rec.Body)
	return string(page)
}

// The "i" button on a box summon opens /web/<lang>/gacha/box, not an empty page.
func TestBoxSummonInfoIsNotEmpty(t *testing.T) {
	if page := boxPage(t, "/web/en/gacha/box?gachaId=200001&nowPlayingId=200001&userId=1"); !strings.Contains(page, "SUMMONS DETAILS") {
		t.Fatalf("box page:\n%s", page)
	}
}

// An event summon's box page lists every level's prizes, its targets, the
// player's level and what is left in it, and the shared prizes; not the
// premium pool's rates.
func TestEventSummonBoxPage(t *testing.T) {
	holder, users := harness(t)
	bunkerHolder = holder
	defer func() { bunkerHolder = nil }()
	users.user.EnsureMaps()
	users.user.Gacha.BannerStates[329001] = store.GachaBannerState{GachaId: 329001, BoxNumber: 2, BoxDrewCounts: map[int32]int32{0: 1}}
	SetWebUsers(users)
	defer SetWebUsers(nil)
	page := boxPage(t, "/web/en/gacha/box?gachaId=329002&nowPlayingId=329002&userId=1")
	for _, want := range []string{"LEVEL 1", "LEVEL 7", "Your level", "0 of 1 left", "target", "SHARED PRIZES", "35%"} {
		if !strings.Contains(page, want) {
			t.Fatalf("missing %q in:\n%s", want, page)
		}
	}
	if strings.Contains(page, "ALL ITEMS") || strings.Contains(page, "FEATURED") {
		t.Fatal("event summon shows the premium pool's rates")
	}
}

// Mama's Dream draws only from its prizes: no premium pool rates.
func TestPrizeBoxPageHasNoPoolRates(t *testing.T) {
	holder, _ := harness(t)
	bunkerHolder = holder
	defer func() { bunkerHolder = nil }()
	for _, url := range []string{"/web/en/gacha/box?gachaId=200001&nowPlayingId=200001", "/web/en/gacha-details?gachaId=200001"} {
		page := boxPage(t, url)
		if !strings.Contains(page, "PRIZES") || strings.Contains(page, "ALL ITEMS") || strings.Contains(page, "FEATURED") {
			t.Fatalf("%s:\n%s", url, page)
		}
	}
}

// An event summon's dates are its event's run: the one open now, else the
// next, else the last; never a start from one run and an end from another.
func TestEventSummonPeriod(t *testing.T) {
	day := int64(24 * 60 * 60 * 1000)
	runs := [][2]int64{{100 * day, 110 * day}, {300 * day, 290 * day}, {200 * day, 215 * day}}
	for _, c := range []struct {
		now  int64
		want string
	}{
		{105 * day, "1970/04/11 – 1970/04/21"},  // open now
		{150 * day, "1970/07/20 – 1970/08/04"},  // the next
		{400 * day, "1970/07/20 – 1970/08/04"},  // the last
	} {
		if got := eventPeriodHTML(runs, c.now); !strings.Contains(got, c.want) {
			t.Errorf("now day %d: %s, want %s", c.now/day, got, c.want)
		}
	}
	if got := eventPeriodHTML([][2]int64{{300 * day, 290 * day}}, 0); !strings.Contains(got, "Opens when its event runs") {
		t.Errorf("no run: %s", got)
	}
}

// The "i" button opens the summon's notice when it has one; the Rates button
// (tab=Rate) keeps the summon's details.
func TestBoxSummonInfoOpensItsNotice(t *testing.T) {
	holder, _ := harness(t)
	bunkerHolder = holder
	defer func() { bunkerHolder = nil }()
	SetNotices(NewNotices(writeNoticePack(t), func() int64 { return 5_000 }))
	defer SetNotices(nil)
	s := &OctoHTTPServer{}
	rec := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/web/en/gacha/box?gachaId=613&nowPlayingId=613&userId=1", nil)
	s.handleWebAPI(rec, r, r.URL.Path)
	if loc := rec.Header().Get("Location"); rec.Code != 302 || loc != "/en/information/?informationId=10&isIngame=1" {
		t.Fatalf("i button: %d %q", rec.Code, loc)
	}
	if page := boxPage(t, "/web/en/gacha/box?gachaId=613&nowPlayingId=613&tab=Rate"); !strings.Contains(page, "SUMMONS DETAILS") && !strings.Contains(page, "<h2>COST</h2>") {
		t.Fatalf("Rates button:\n%.300s", page)
	}
}
