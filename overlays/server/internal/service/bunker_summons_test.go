package service

import (
	"testing"

	"lunar-tear/server/internal/gacha"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func catalogById(t *testing.T) (map[int32]store.GachaCatalogEntry, *gacha.GachaHandler) {
	cats := loadMaster(t).Get()
	out := map[int32]store.GachaCatalogEntry{}
	for _, e := range cats.GachaEntries {
		out[e.GachaId] = e
	}
	return out, cats.GachaHandler
}

func TestSummonCatalogRules(t *testing.T) {
	byId, _ := catalogById(t)
	if _, ok := byId[45]; !ok || byId[45].EndDatetime > 2_000_000_000_000 {
		t.Skip("needs the original master data")
	}
	// Multi-step summons: one entry each, steps from the game's step pages.
	if e := byId[9000041]; e.GachaModeType != model.GachaModeStepup || e.MaxStepNumber != 5 || len(e.PricePhases) != 5 {
		t.Errorf("Festive Dress step-up: mode %d steps %d phases %d", e.GachaModeType, e.MaxStepNumber, len(e.PricePhases))
	} else {
		for i, want := range []int32{3000, 0, 2000, 0, 5000} {
			if p := e.PricePhases[i]; p.Price != want {
				t.Errorf("Festive Dress step %d costs %d, the game says %d", i+1, p.Price, want)
			}
		}
	}
	if e := byId[9000035]; e.MedalConsumableItemId != 8021 || e.MaxStepNumber != 5 {
		t.Errorf("Yuletide step-up: medal %d steps %d", e.MedalConsumableItemId, e.MaxStepNumber)
	}
	// Known medals for summons without a medal row.
	for gid, item := range map[int32]int32{535: 8192, 401: 8087, 510001: 8030, 583: 8222} {
		if byId[gid].MedalConsumableItemId != item {
			t.Errorf("summon %d medal %d, want %d", gid, byId[gid].MedalConsumableItemId, item)
		}
	}
	// Special summons.
	free := byId[64]
	if len(free.PricePhases) != 1 || free.PricePhases[0].Price != 0 || free.PricePhases[0].LimitExecCount != 1 || free.GachaAutoResetType != model.GachaAutoResetDaily {
		t.Errorf("free summon: %+v", free)
	}
	g := byId[66].PricePhases
	if len(g) != 1 || g[0].PriceType != model.PriceTypePaidGem || g[0].FixedRarityMin != model.RaritySSRare || g[0].LimitExecCount != 1 {
		t.Errorf("paid guaranteed summon: %+v", g)
	}
	for _, p := range byId[153].PricePhases {
		if p.PriceType != model.PriceTypePaidGem {
			t.Errorf("paid-only summon 153 phase %+v", p)
		}
	}
	if byId[153].MedalConsumableItemId == 0 {
		t.Error("paid-only summon lost its medal")
	}
	// Bonus summons whose only rows are 2099 placeholders stay out; those with
	// a notice run with its rules (Monthly Bonus Summons, Mar. 2023: notice 1040).
	for _, skipped := range []int32{69, 93} {
		if _, ok := byId[skipped]; ok {
			t.Errorf("bonus summon %d offered", skipped)
		}
	}
	if p := byId[486].PricePhases; len(p) != 1 || p[0].Price != 3000 || p[0].DrawCount != 10 || p[0].LimitExecCount != 5 {
		t.Errorf("Monthly Bonus Summons 486: %+v", p)
	}
	if _, ok := byId[534]; !ok {
		t.Error("newcomer pack summon 534 not offered")
	}
	// Reruns parked in 2099 take their shop's dates (the original's; the
	// everything-open data moves the medal's conversion date out).
	if e := byId[159]; e.EndDatetime < 1_700_000_000_000 && (e.StartDatetime != 1652148000000 || e.EndDatetime != 1655085599000) {
		t.Errorf("FFXIV rerun %d-%d", e.StartDatetime, e.EndDatetime)
	}
	// Chapter summons no longer use Mama's Dream ids.
	chapters := 0
	for id, e := range byId {
		if e.GachaLabelType == model.GachaLabelChapter {
			chapters++
			if id < model.ChapterGachaIdBase {
				t.Errorf("chapter summon %d below the new base", id)
			}
		}
	}
	if chapters != 25 {
		t.Errorf("%d chapter summons, want 25", chapters)
	}
}

// Summons that start together get their own featured items (their shop's).
func TestFeaturedFromOwnShop(t *testing.T) {
	cats := loadMaster(t).Get()
	f := cats.GachaHandler.Pool.FeaturedByGacha
	if _, ok := f[45]; !ok {
		t.Skip("needs the original master data")
	}
	if n := len(f[45].Costumes); n == 0 || n > 6 {
		t.Errorf("Automata Vol. 1 has %d featured costumes, want its shop's (at most 6)", n)
	}
	same := len(f[45].Costumes) == len(f[46].Costumes)
	for i := 0; same && i < len(f[45].Costumes); i++ {
		same = f[45].Costumes[i].PossessionId == f[46].Costumes[i].PossessionId
	}
	if len(f[46].Costumes) == 0 {
		t.Error("Automata Vol. 2 has no featured costumes")
	}
	_ = same // Vol. 1 and 2 share one shard shop, so they may match.
	for _, pair := range [][2]int32{{176, 180}, {509, 511}} {
		a, b := f[pair[0]], f[pair[1]]
		if len(a.Costumes) > 0 && len(b.Costumes) > 0 && a.Costumes[0].PossessionId == b.Costumes[0].PossessionId && len(a.Costumes) == len(b.Costumes) {
			t.Errorf("summons %d and %d still share featured items", pair[0], pair[1])
		}
	}
}

func TestLimitedDraws(t *testing.T) {
	byId, handler := catalogById(t)
	free, ok := byId[64]
	if !ok {
		t.Skip("needs the original master data")
	}
	defer gametime.SetCalendar(nil)
	day := free.StartDatetime + 3600_000
	gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: 1, JumpMillis: day - gametime.Now().UnixMilli(), Speed: 1})
	u := store.UserState{}
	u.EnsureMaps()
	phase := free.PricePhases[0].PhaseId
	if _, err := handler.HandleDraw(&u, free, phase, 1); err != nil {
		t.Fatalf("first free draw: %v", err)
	}
	if _, err := handler.HandleDraw(&u, free, phase, 1); err == nil {
		t.Fatal("second free draw the same day allowed")
	}
	gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: 1, JumpMillis: day + 86400_000 - gametime.Now().UnixMilli(), Speed: 1})
	if _, err := handler.HandleDraw(&u, free, phase, 1); err != nil {
		t.Fatalf("free draw the next day: %v", err)
	}
	// A one-time guaranteed summon stays used.
	g := byId[66]
	u.Gem.PaidGem = 10000
	if _, err := handler.HandleDraw(&u, g, g.PricePhases[0].PhaseId, 1); err != nil {
		t.Fatalf("guaranteed draw: %v", err)
	}
	if _, err := handler.HandleDraw(&u, g, g.PricePhases[0].PhaseId, 1); err == nil {
		t.Fatal("one-time summon drawn twice")
	}
}

func TestChapterSummonProgressMoves(t *testing.T) {
	u := store.UserState{}
	u.EnsureMaps()
	u.Gacha.BannerStates[200005] = store.GachaBannerState{GachaId: 200005, BoxNumber: 3}
	u.Gacha.BannerStates[45] = store.GachaBannerState{GachaId: 45, MedalCount: 7}
	store.UpgradeChapterGachaIds(&u)
	if _, old := u.Gacha.BannerStates[200005]; old || u.Gacha.BannerStates[model.ChapterGachaIdBase+5].BoxNumber != 3 {
		t.Fatalf("chapter progress not moved: %v", u.Gacha.BannerStates)
	}
	if u.Gacha.BannerStates[45].MedalCount != 7 {
		t.Fatal("other summon changed")
	}
	u.Gacha.BannerStates[200005] = store.GachaBannerState{GachaId: 200005}
	store.UpgradeChapterGachaIds(&u)
	if _, kept := u.Gacha.BannerStates[200005]; !kept {
		t.Fatal("ran twice")
	}
}

// Summons without a banner row (weekly, paid multi-step, Fortune's and
// Blessed Dress) are offered on their shop's dates when the client has art.
func TestBannerlessSummons(t *testing.T) {
	byId, _ := catalogById(t)
	w, ok := byId[10001]
	if !ok {
		t.Fatal("weekly summon 10001 not offered")
	}
	if w.EndDatetime > 1_700_000_000_000 {
		t.Skip("needs the original master data")
	}
	if w.BannerAssetName != "limited_10001" || w.StartDatetime != 1647914400000 || w.EndDatetime != 1648432799000 || w.CeilingCount != 150 {
		t.Errorf("weekly summon 10001: %+v", w)
	}
	p := byId[590001]
	if p.GachaModeType != model.GachaModeStepup || p.BannerAssetName != "step_up_590001" || p.CeilingCount != 50 || p.PricePhases[0].PriceType != model.PriceTypePaidGem {
		t.Errorf("paid step-up 590001: %+v", p)
	}
	for _, id := range []int32{145, 402, 10106, 612001} {
		if _, ok := byId[id]; !ok {
			t.Errorf("summon %d not offered", id)
		}
	}
	// The last weekly summons (04-30-2023) have no art; they reran Lars's and
	// Griff's of 03-19 and show those.
	for id, art := range map[int32]string{10107: "limited_10094", 10108: "limited_10095"} {
		if e, ok := byId[id]; !ok || e.BannerAssetName != art {
			t.Errorf("weekly summon %d: %+v", id, e)
		}
	}
	for _, id := range []int32{617, 10016, 9000040} {
		if _, ok := byId[id]; ok {
			t.Errorf("summon %d without art offered", id)
		}
	}
}
