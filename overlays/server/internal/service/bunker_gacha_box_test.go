package service

import (
	"database/sql"
	"fmt"
	"io"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
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
		{105 * day, "1970/04/11 – 1970/04/21"}, // open now
		{150 * day, "1970/07/20 – 1970/08/04"}, // the next
		{400 * day, "1970/07/20 – 1970/08/04"}, // the last
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

// archiveText stands in for the Archive's English text until the test ends.
func archiveText(t *testing.T, text map[string]string) {
	t.Helper()
	dir := t.TempDir()
	db, err := sql.Open("sqlite", filepath.Join(dir, "archive.db"))
	if err != nil {
		t.Fatal(err)
	}
	db.Exec(`CREATE TABLE text (key TEXT PRIMARY KEY, value TEXT)`)
	for k, v := range text {
		db.Exec(`INSERT INTO text VALUES (?, ?)`, k, v)
	}
	db.Close()
	saved := archivePaths
	archivePaths = []string{filepath.Join(dir, "archive.db")}
	t.Cleanup(func() { archivePaths = saved })
}

// An event summon's cost names each of its tickets.
func TestEventSummonCostNamesItsTickets(t *testing.T) {
	holder, _ := harness(t)
	bunkerHolder = holder
	defer func() { bunkerHolder = nil }()
	box, _, _ := masterdata.EventSummonFor(329001)
	text := map[string]string{}
	rows, _ := utils.ReadTable[masterdata.EntityMConsumableItem]("m_consumable_item")
	for _, c := range rows {
		for i, ticket := range box.Tickets {
			if c.ConsumableItemId == ticket {
				text[fmt.Sprintf("consumable_item.name.%d%03d", c.AssetCategoryId, c.AssetVariationId)] = fmt.Sprintf("Ticket Tier %d", i+1)
			}
		}
	}
	if len(text) != len(box.Tickets) {
		t.Fatalf("tickets %v: %d named", box.Tickets, len(text))
	}
	archiveText(t, text)
	page := boxPage(t, "/web/en/gacha-details?gachaId=329001")
	for i := range box.Tickets {
		if want := fmt.Sprintf("10 × Ticket Tier %d", i+1); !strings.Contains(page, want) {
			t.Fatalf("missing %q in:\n%.2000s", want, page)
		}
	}
}

// A summon without a title in the game text is named by its notice.
func TestSummonTitleFromItsNotice(t *testing.T) {
	holder, _ := harness(t)
	bunkerHolder = holder
	defer func() { bunkerHolder = nil }()
	SetNotices(NewNotices(writeNoticePack(t), func() int64 { return 5_000 }))
	defer SetNotices(nil)
	archiveText(t, nil)
	if page := boxPage(t, "/web/en/gacha-details?gachaId=613"); !strings.Contains(page, "<h1>Abstract Savior Summons</h1>") {
		t.Fatalf("%.600s", page)
	}
}

// The DQX crossover's free summons (554) show the three characters its appeal
// art shows, so its panel has more than one page; none of them is featured.
func TestFreeSummonShowsItsArtCharacters(t *testing.T) {
	holder, _ := harness(t)
	for _, e := range holder.Get().GachaEntries {
		if e.GachaId != 554 {
			continue
		}
		if len(e.PromotionItems) != 3 {
			t.Fatalf("554 cards: %+v", e.PromotionItems)
		}
		for _, p := range e.PromotionItems {
			if p.IsTarget || p.BonusPossessionId == 0 {
				t.Fatalf("554 card: %+v", p)
			}
		}
		return
	}
	t.Fatal("no summon 554")
}

// The barrier weapon summons (notice 962, Vol. 1-3): every ★4 weapon has the
// volume's rank 4 barrier skill, the weapons their art shows among them.
func TestBarrierWeaponSummons(t *testing.T) {
	holder, _ := harness(t)
	c := holder.Get()
	for id, want := range map[int32][]int32{468: {320131, 350201, 350391}, 469: {330361, 330281, 340331}, 470: {320251, 350311, 340511}} {
		bp := c.GachaPool.BannerPools[id]
		if bp == nil {
			t.Fatalf("no summon %d", id)
		}
		lineup := map[int32]bool{}
		for _, w := range bp.WeaponsByRarity[40] {
			lineup[w.PossessionId] = true
		}
		if len(lineup) < 70 {
			t.Fatalf("%d: %d ★4 weapons", id, len(lineup))
		}
		for _, w := range want {
			if !lineup[w] {
				t.Errorf("%d: art weapon %d not in its lineup", id, w)
			}
		}
		for _, e := range c.GachaEntries {
			if e.GachaId == id && len(e.PromotionItems) != 3 {
				t.Errorf("%d: cards %+v", id, e.PromotionItems)
			}
		}
	}
}

// Summons whose art or notice names a lineup no longer draw from the standard
// pool alone: Bloody daily free summon, Abyssal Weapon, a fire weapon
// summon, the Healer & Support summons.
func TestSummonLineupsFromArtAndNotices(t *testing.T) {
	holder, _ := harness(t)
	c := holder.Get()
	ss := int32(40)
	bp := func(id int32) *masterdata.BannerPool {
		b := c.GachaPool.BannerPools[id]
		if b == nil {
			t.Fatalf("no summon %d", id)
		}
		return b
	}
	if l := bp(456).CostumesByRarity[ss]; len(l) != 10 {
		t.Errorf("456 ★4 characters: %d, want the 10 Bloody costumes", len(l))
	}
	if l := bp(424).CostumesByRarity[ss]; len(l) != 1 || l[0].PossessionId != 32020 {
		t.Errorf("424 ★4 characters: %+v", l)
	}
	if len(bp(71).Featured) == 0 {
		t.Error("71 has no featured fire weapons")
	}
	for _, f := range bp(71).Featured {
		if masterdata.ElementOf(f) != 2 {
			t.Errorf("71 featured %d is not fire", f.PossessionId)
		}
	}
	if l := bp(9505071).WeaponsByRarity[ss]; len(l) != 33 {
		t.Errorf("9505071 ★4 weapons: %d", len(l))
	}
	for _, e := range c.GachaEntries {
		if e.GachaId == 9505061 {
			if r, _ := masterdata.PhaseRuleFor(e.PricePhases[0].PhaseId); r.Guar != "r4w" || e.GachaAutoResetType == 0 {
				t.Errorf("9505061: guarantee %q reset %d", r.Guar, e.GachaAutoResetType)
			}
		}
	}
}

// Step-up summons take their steps from their art: 525001 was one 50x pull
// in the game data; 522001 has three steps, not five; bonuses and guarantees
// are per step.
func TestStepUpsFromArt(t *testing.T) {
	holder, _ := harness(t)
	want := map[int32]int32{514001: 4, 519001: 3, 522001: 3, 525001: 4, 9000016: 5, 9000054: 5, 9000073: 5}
	for _, e := range holder.Get().GachaEntries {
		n, ok := want[e.GachaId]
		if !ok {
			continue
		}
		delete(want, e.GachaId)
		if e.MaxStepNumber != n || len(e.PricePhases) != int(n) {
			t.Errorf("%d: %d steps, %d phases, want %d", e.GachaId, e.MaxStepNumber, len(e.PricePhases), n)
			continue
		}
		if e.GachaId == 514001 {
			first := e.PricePhases[0]
			if r, _ := masterdata.PhaseRuleFor(first.PhaseId); r.Guar != "r4w" || len(first.Bonuses) != 2 || first.Price != 3000 {
				t.Errorf("514001 step 1: %+v %q", first, r.Guar)
			}
		}
	}
	if len(want) > 0 {
		t.Errorf("missing step-ups %v", want)
	}
}

// Added summons take their steps from their own entries: Abyssal Weapon's
// ★4 rate x1.5, the Bloody daily summon free once a day.
func TestAddedSummonStepsFromArt(t *testing.T) {
	holder, _ := harness(t)
	for _, e := range holder.Get().GachaEntries {
		switch e.GachaId {
		case 424:
			if r, _ := masterdata.PhaseRuleFor(e.PricePhases[0].PhaseId); r.Rate != 1.5 || !r.Feat4 {
				t.Errorf("424 rule %+v", r)
			}
		case 456:
			if len(e.PricePhases) != 1 || e.PricePhases[0].Price != 0 || e.GachaAutoResetType == 0 {
				t.Errorf("456 phases %+v reset %d", e.PricePhases, e.GachaAutoResetType)
			}
		}
	}
}

// Summons recovered from their art and the event guide's dates: the DQX
// Oathbound Exile step-up, the New Year Countdown Vol. 2, the 220 free summons.
func TestRecoveredSummons(t *testing.T) {
	holder, _ := harness(t)
	c := holder.Get()
	got := map[int32]bool{}
	for _, e := range c.GachaEntries {
		switch e.GachaId {
		case 586001:
			if e.MaxStepNumber != 3 {
				t.Errorf("586001: %d steps", e.MaxStepNumber)
			}
		case 450:
			if r, _ := masterdata.PhaseRuleFor(e.PricePhases[0].PhaseId); r.Rate != 1.5 || !r.Feat4 {
				t.Errorf("450 rule %+v", r)
			}
		case 144:
			if e.PricePhases[0].Price != 0 || len(e.PromotionItems) != 3 {
				t.Errorf("144: %+v cards %d", e.PricePhases, len(e.PromotionItems))
			}
		}
		got[e.GachaId] = true
	}
	for _, id := range []int32{123, 413, 417, 473, 474, 438, 444, 445, 467, 471, 546, 476, 144, 450, 451, 557001, 558001, 560001, 563001, 523001, 531001, 581001, 582001, 586001, 587001, 900003} {
		if !got[id] {
			t.Errorf("summon %d missing", id)
		}
	}
	if bp := c.GachaPool.BannerPools[586001]; bp == nil || len(bp.Featured) == 0 {
		t.Error("586001 features nothing")
	}
}

// Twins the notices tell apart: Bunker's paid Abyssal Assassin is 413 (its
// art), 474 is Abyssal Festival Vol. 3; 416 is the regular Abstract Ruler
// summon and 417 the paid one; 428 is the Subjugation Conquest Summons.
func TestSummonTwinsFromNotices(t *testing.T) {
	holder, _ := harness(t)
	c := holder.Get()
	only := func(id int32, want ...int32) {
		got := map[int32]bool{}
		for _, x := range c.GachaPool.BannerPools[id].CostumesByRarity[40] {
			got[x.PossessionId] = true
		}
		if len(got) != len(want) {
			t.Errorf("%d: %d ★4 characters, want %v", id, len(got), want)
		}
		for _, w := range want {
			if !got[w] {
				t.Errorf("%d: no %d", id, w)
			}
		}
	}
	only(474, 32020, 33017, 31019)
	only(473, 34032, 32015, 32019)
	only(445, 32013, 31017, 34027)
	for _, e := range c.GachaEntries {
		r, _ := masterdata.PhaseRuleFor(e.PricePhases[0].PhaseId)
		switch e.GachaId {
		case 413, 417:
			if e.PricePhases[0].PriceType != 3 || e.PricePhases[0].LimitExecCount != 10 {
				t.Errorf("%d: %+v", e.GachaId, e.PricePhases[0])
			}
		case 416:
			if e.PricePhases[0].Price != 300 {
				t.Errorf("416 is not the regular summon: %+v", e.PricePhases)
			}
		case 428:
			if r.Rate != 2 || len(e.PricePhases[0].Bonuses) != 4 {
				t.Errorf("428: %+v %+v", r, e.PricePhases[0])
			}
		case 449:
			if r.Rate != 1.5 {
				t.Errorf("449 rate %v", r.Rate)
			}
		}
	}
}

// A summon's rule can name its notice over the notice pack's link: the
// regular Abstract Ruler summon (416) opens notice 733, not the paid one's.
func TestRuleNamesTheSummonsNotice(t *testing.T) {
	holder, _ := harness(t)
	for _, e := range holder.Get().GachaEntries {
		switch e.GachaId {
		case 416:
			if e.InformationId != 733 {
				t.Errorf("416 notice %d", e.InformationId)
			}
		case 428:
			if e.InformationId != 801 {
				t.Errorf("428 notice %d", e.InformationId)
			}
		}
	}
}

// Summons Details takes a summon's title from summon_rules.json's titles
// over the game text where that text is wrong (416's says it is the paid
// one) or missing or Japanese.
func TestSummonTitlesFixed(t *testing.T) {
	holder, _ := harness(t)
	bunkerHolder = holder
	defer func() { bunkerHolder = nil }()
	archiveText(t, map[string]string{"gacha.title.limited_416": "Paid Only: Abstract Ruler Summons"})
	for id, want := range map[string]string{"416": "Abstract Ruler Summons", "428": "Subjugation Conquest Summons", "586001": "Paid Only: Oathbound Exile Multi-Step Summons"} {
		if page := boxPage(t, "/web/en/gacha-details?gachaId="+id); !strings.Contains(page, "<h1>"+want+"</h1>") {
			t.Errorf("%s: %.400s", id, page[strings.Index(page, "<body>"):])
		}
	}
}

// The box page's redirect keeps a language only when the path has one, and a
// notice title's "On Now" or "Updated" is dropped from a summon's title.
func TestBoxRedirectLanguageAndNoticeTitleSuffixes(t *testing.T) {
	if got := webLanguage("/web/gacha/box"); got != "en" {
		t.Errorf("no language segment: %q", got)
	}
	if got := webLanguage("/web/ja/gacha/box"); got != "ja" {
		t.Errorf("ja: %q", got)
	}
	for in, want := range map[string]string{"X Summons On Now": "X Summons", "X Summons Updated": "X Summons", "X Summons": "X Summons"} {
		if got := trimNoticeTitle(in); got != want {
			t.Errorf("%q -> %q", in, got)
		}
	}
}
