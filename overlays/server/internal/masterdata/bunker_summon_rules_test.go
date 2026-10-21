package masterdata

import (
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func basicEntry(id int32) store.GachaCatalogEntry {
	return store.GachaCatalogEntry{GachaId: id, GachaModeType: model.GachaModeBasic, GachaAutoResetType: model.GachaAutoResetNone,
		PricePhases: buildPremiumBasicPricePhases(id)}
}

func TestSummonRulePricesARegularSummon(t *testing.T) {
	rules := map[int32]summonRule{489: {Steps: []ruleStep{
		{Draws: 1, Price: 300, Cur: "gems"},
		{Draws: 10, Price: 3000, Cur: "paid", Limit: 5, Guar: "r3w"},
	}}}
	got := applySummonRules([]store.GachaCatalogEntry{basicEntry(489)}, rules)[0]
	if len(got.PricePhases) != 3 {
		t.Fatalf("phases: %+v", got.PricePhases)
	}
	one, ten, ticket := got.PricePhases[0], got.PricePhases[1], got.PricePhases[2]
	if one.PhaseId != 4891 || one.Price != 300 || one.PriceType != model.PriceTypeGem || one.DrawCount != 1 || one.FixedCount != 0 {
		t.Fatalf("single draw: %+v", one)
	}
	if ten.PhaseId != 4892 || ten.Price != 3000 || ten.PriceType != model.PriceTypePaidGem || ten.DrawCount != 10 ||
		ten.LimitExecCount != 5 || ten.FixedRarityMin != model.RaritySRare || ten.FixedCount != 1 {
		t.Fatalf("ten draws: %+v", ten)
	}
	// The premium ticket draw the game data gives a regular summon stays.
	if ticket.PhaseId != 4893 || ticket.PriceType != model.PriceTypeConsumableItem || ticket.PriceId != model.ConsumableIdPremiumTicket {
		t.Fatalf("ticket draw: %+v", ticket)
	}
}

func TestSummonRulePricesAStepUp(t *testing.T) {
	entry := store.GachaCatalogEntry{GachaId: 533001, GachaModeType: model.GachaModeStepup, MaxStepNumber: 5,
		PricePhases: buildStepUpPricePhases(533001, 5, nil)}
	rules := map[int32]summonRule{533001: {Steps: []ruleStep{
		{Step: 1, Draws: 10, Price: 3000, Cur: "paid", Guar: "r4w"},
		{Step: 2, Draws: 10, Price: 0, Cur: "free", Guar: "r3w"},
		{Step: 3, Draws: 10, Price: 3000, Cur: "paid", Guar: "r4c"},
	}}}
	got := applySummonRules([]store.GachaCatalogEntry{entry}, rules)[0]
	if got.MaxStepNumber != 3 || len(got.PricePhases) != 3 {
		t.Fatalf("steps: max %d, phases %+v", got.MaxStepNumber, got.PricePhases)
	}
	for i, p := range got.PricePhases {
		if p.StepNumber != int32(i+1) || p.LimitExecCount != 1 || p.PhaseId != 533001*10+int32(i+1) {
			t.Fatalf("step %d: %+v", i+1, p)
		}
	}
	if s2 := got.PricePhases[1]; s2.Price != 0 || s2.PriceType != model.PriceTypeGem {
		t.Fatalf("free step: %+v", s2)
	}
	if s1 := got.PricePhases[0]; s1.PriceType != model.PriceTypePaidGem || s1.FixedRarityMin != model.RaritySSRare || s1.FixedCount != 1 {
		t.Fatalf("step 1: %+v", s1)
	}
}

func TestSummonRuleOfTheWrongShapeIsIgnored(t *testing.T) {
	// Steps for a summon the game data has as a regular one (its step pages
	// have no art), and plain draws for a step-up: both keep their prices.
	basic := basicEntry(10)
	step := store.GachaCatalogEntry{GachaId: 11, GachaModeType: model.GachaModeStepup, MaxStepNumber: 5, PricePhases: buildStepUpPricePhases(11, 5, nil)}
	rules := map[int32]summonRule{
		10: {Steps: []ruleStep{{Step: 1, Draws: 10, Price: 1500, Cur: "paid"}}},
		11: {Steps: []ruleStep{{Draws: 10, Price: 3000, Cur: "gems"}}},
	}
	got := applySummonRules([]store.GachaCatalogEntry{basic, step}, rules)
	if got[0].PricePhases[1].Price != model.PremiumMultiPullPrice || got[1].MaxStepNumber != 5 || got[1].PricePhases[0].StepNumber != 1 {
		t.Fatalf("changed: %+v / %+v", got[0].PricePhases, got[1].PricePhases)
	}
}

func TestSummonRuleDailyAndGuarantees(t *testing.T) {
	rules := map[int32]summonRule{7: {Steps: []ruleStep{
		{Draws: 10, Price: 0, Cur: "free", Daily: true, Guar: "set10:feat"},
		{Draws: 10, Price: 3000, Cur: "gems", Guar: "none"},
	}}}
	got := applySummonRules([]store.GachaCatalogEntry{basicEntry(7)}, rules)[0]
	if got.GachaAutoResetType != model.GachaAutoResetDaily || got.GachaAutoResetPeriod != 1 {
		t.Fatalf("daily: %+v", got)
	}
	if p := got.PricePhases[0]; p.LimitExecCount != 1 || p.FixedRarityMin != model.RaritySSRare || p.FixedCount != 1 {
		t.Fatalf("daily free ★4: %+v", p)
	}
	if p := got.PricePhases[1]; p.FixedCount != 0 {
		t.Fatalf("nothing guaranteed: %+v", p)
	}
}

func TestEmbeddedSummonRulesAreValid(t *testing.T) {
	rules, err := loadSummonRules()
	if err != nil {
		t.Fatal(err)
	}
	if len(rules) < 150 {
		t.Fatalf("only %d summon rules", len(rules))
	}
	for id, r := range rules {
		if (len(r.Steps) == 0 && r.Featured == nil) || len(r.Steps) > 9 {
			t.Fatalf("summon %d: %d steps, featured %v", id, len(r.Steps), r.Featured)
		}
		stepped := len(r.Steps) > 0 && r.Steps[0].Step > 0
		for i, s := range r.Steps {
			if s.Draws <= 0 || s.Price < 0 || priceTypeOf(s.Cur) == model.PriceTypeUnknown {
				t.Fatalf("summon %d step %d: %+v", id, i, s)
			}
			if stepped && s.Step != int32(i+1) {
				t.Fatalf("summon %d: steps out of order: %+v", id, r.Steps)
			}
		}
	}
}

func featuredPool() *GachaCatalog {
	c1 := GachaPoolItem{PossessionType: int32(model.PossessionTypeCostume), PossessionId: 1001, RarityType: model.RaritySSRare, CharacterId: 1}
	c2 := GachaPoolItem{PossessionType: int32(model.PossessionTypeCostume), PossessionId: 1002, RarityType: model.RaritySSRare, CharacterId: 2}
	w1 := GachaPoolItem{PossessionType: int32(model.PossessionTypeWeapon), PossessionId: 2001, RarityType: model.RaritySSRare}
	w2 := GachaPoolItem{PossessionType: int32(model.PossessionTypeWeapon), PossessionId: 2002, RarityType: model.RaritySSRare}
	return &GachaCatalog{
		CostumeById:      map[int32]GachaPoolItem{1001: c1, 1002: c2},
		WeaponById:       map[int32]GachaPoolItem{2001: w1, 2002: w2},
		CostumeWeaponMap: map[int32]int32{1001: 2001},
		FeaturedByGacha:  map[int32]FeaturedSet{5: {Costumes: []GachaPoolItem{c2}}, 6: {Costumes: []GachaPoolItem{c2}}},
	}
}

func TestRuleFeaturedReplacesTheGameDataLineup(t *testing.T) {
	pool := featuredPool()
	pool.applyRuleFeatured(map[int32]summonRule{5: {Featured: &ruleFeatured{Costumes: []int32{1001, 9999}, Weapons: []int32{2001, 2002}}}})
	fs := pool.FeaturedByGacha[5]
	if len(fs.Costumes) != 1 || fs.Costumes[0].PossessionId != 1001 {
		t.Fatalf("costumes: %+v", fs.Costumes)
	}
	// 2001 comes with costume 1001 (BuildBannerPools adds it); listing it again would double its weight.
	if len(fs.Weapons) != 1 || fs.Weapons[0].PossessionId != 2002 {
		t.Fatalf("weapons: %+v", fs.Weapons)
	}
	if got := pool.FeaturedByGacha[6]; len(got.Costumes) != 1 || got.Costumes[0].PossessionId != 1002 {
		t.Fatalf("a summon without a rule changed: %+v", got)
	}
}

func TestRuleFeaturedWithUnknownItemsKeepsTheLineup(t *testing.T) {
	pool := featuredPool()
	pool.applyRuleFeatured(map[int32]summonRule{5: {Featured: &ruleFeatured{Costumes: []int32{9999}}}})
	if got := pool.FeaturedByGacha[5]; len(got.Costumes) != 1 || got.Costumes[0].PossessionId != 1002 {
		t.Fatalf("lineup replaced by nothing: %+v", got)
	}
}

func TestOutsideSourceLineupKeepsTheFeaturedWeapons(t *testing.T) {
	pool := featuredPool()
	w2 := pool.WeaponById[2002]
	pool.FeaturedByGacha[5] = FeaturedSet{Costumes: []GachaPoolItem{pool.CostumeById[1002]}, Weapons: []GachaPoolItem{w2}}
	// Outside sources name characters only: the weapons stay.
	pool.applyRuleFeatured(map[int32]summonRule{5: {Featured: &ruleFeatured{Costumes: []int32{1001}, Src: "web: tweet"}}})
	if fs := pool.FeaturedByGacha[5]; len(fs.Costumes) != 1 || fs.Costumes[0].PossessionId != 1001 || len(fs.Weapons) != 1 || fs.Weapons[0].PossessionId != 2002 {
		t.Fatalf("outside source: %+v", fs)
	}
	// A notice lists the whole lineup: no weapons listed means none featured.
	pool.applyRuleFeatured(map[int32]summonRule{5: {Featured: &ruleFeatured{Costumes: []int32{1002}, Src: "notice 1"}}})
	if fs := pool.FeaturedByGacha[5]; len(fs.Costumes) != 1 || fs.Costumes[0].PossessionId != 1002 || len(fs.Weapons) != 0 {
		t.Fatalf("notice: %+v", fs)
	}
}

func TestSummonRuleBonusItems(t *testing.T) {
	entry := store.GachaCatalogEntry{GachaId: 527001, GachaModeType: model.GachaModeStepup, MaxStepNumber: 3, PricePhases: buildStepUpPricePhases(527001, 3, nil)}
	rules := map[int32]summonRule{527001: {Steps: []ruleStep{
		{Step: 1, Draws: 10, Price: 3000, Cur: "paid", Items: []ruleItem{{Type: 6, Id: 2003, Count: 100}, {Type: 5, Id: 200004, Count: 2180}}},
		{Step: 2, Draws: 10, Price: 3000, Cur: "paid"},
		{Step: 3, Draws: 10, Price: 3000, Cur: "paid", Items: []ruleItem{{Type: 5, Id: 311003, Count: 10}}},
	}}}
	got := applySummonRules([]store.GachaCatalogEntry{entry}, rules)[0]
	b := got.PricePhases[0].Bonuses
	if len(b) != 2 || b[0] != (store.GachaBonusEntry{PossessionType: 6, PossessionId: 2003, Count: 100}) || b[1].PossessionId != 200004 || b[1].Count != 2180 {
		t.Fatalf("step 1 bonuses: %+v", b)
	}
	if len(got.PricePhases[1].Bonuses) != 0 || len(got.PricePhases[2].Bonuses) != 1 {
		t.Fatalf("steps 2/3 bonuses: %+v / %+v", got.PricePhases[1].Bonuses, got.PricePhases[2].Bonuses)
	}
}

func TestPaidTwinsJoinTheCatalog(t *testing.T) {
	regular := basicEntry(489)
	regular.GachaMedalId, regular.MedalConsumableItemId, regular.CeilingCount, regular.SortOrder = 77, 7700, 200, 5000
	regular.StartDatetime, regular.EndDatetime = 1_680_000_000_000, 1_681_000_000_000 // the twin runs with it
	taken := basicEntry(9)
	file := summonRulesFile{New: []newSummon{
		{Id: 490, Asset: "limited_490", Pair: 489, Start: 1_680_000_000_000, End: 1_681_000_000_000, Notice: 1078,
			Steps: []ruleStep{{Draws: 10, Price: 3000, Cur: "paid", Limit: 5, Guar: "r3w"}}},
		{Id: 565001, Asset: "step_up_565001", Pair: 565, Start: 1_690_000_000_000, End: 1_691_000_000_000, Notice: 1152,
			Steps: []ruleStep{{Step: 1, Draws: 10, Price: 1500, Cur: "paid"}, {Step: 2, Draws: 10, Price: 3000, Cur: "paid", Guar: "set10:feat"}}},
		{Id: 9, Asset: "limited_9", Pair: 489, Start: 1, End: 2, Steps: []ruleStep{{Draws: 10, Price: 1, Cur: "paid"}}},
	}}
	got := addNewSummons([]store.GachaCatalogEntry{regular, taken}, file, 0)
	byId := map[int32]store.GachaCatalogEntry{}
	for _, e := range got {
		byId[e.GachaId] = e
	}
	if len(got) != 4 || byId[9].PricePhases[1].Price != model.PremiumMultiPullPrice {
		t.Fatalf("an id the game data already uses was replaced, or a twin is missing: %d entries", len(got))
	}
	twin := byId[490]
	if twin.BannerAssetName != "limited_490" || twin.StartDatetime != 1_680_000_000_000 || twin.EndDatetime != 1_681_000_000_000 ||
		twin.GachaMedalId != 77 || twin.MedalConsumableItemId != 7700 || twin.CeilingCount != 200 || twin.SortOrder != 5000 ||
		twin.InformationId != 1078 || twin.GachaModeType != model.GachaModeBasic || !twin.IsUserGachaUnlock {
		t.Fatalf("twin: %+v", twin)
	}
	if len(twin.PricePhases) != 1 || twin.PricePhases[0].PriceType != model.PriceTypePaidGem || twin.PricePhases[0].LimitExecCount != 5 {
		t.Fatalf("twin draws: %+v", twin.PricePhases)
	}
	step := byId[565001]
	if step.GachaModeType != model.GachaModeStepup || step.MaxStepNumber != 2 || step.GroupId != 565001 || len(step.PricePhases) != 2 ||
		step.PricePhases[1].StepNumber != 2 || step.GachaMedalId != 0 {
		t.Fatalf("step-up twin without a regular summon: %+v", step)
	}
	if r, ok := PhaseRuleFor(step.PricePhases[1].PhaseId); !ok || r.Guar != "set10:feat" {
		t.Fatalf("step 2 rule: %+v %v", r, ok)
	}
}

func TestPaidTwinDatesFollowTheCalendar(t *testing.T) {
	file := summonRulesFile{New: []newSummon{{Id: 490, Asset: "limited_490", Start: 1000, End: 2000, Steps: []ruleStep{{Draws: 10, Price: 3000, Cur: "paid"}}}}}
	got := addNewSummons(nil, file, 500)
	if got[0].StartDatetime != 1500 || got[0].EndDatetime != 2500 {
		t.Fatalf("dates with a calendar shift of 500: %d-%d", got[0].StartDatetime, got[0].EndDatetime)
	}
}

func TestPaidTwinsShareTheirRegularLineup(t *testing.T) {
	pool := featuredPool()
	pool.applyNewFeatured(summonRulesFile{New: []newSummon{{Id: 490, Pair: 5}, {Id: 491, Pair: 404}}})
	if got := pool.FeaturedByGacha[490]; len(got.Costumes) != 1 || got.Costumes[0].PossessionId != 1002 {
		t.Fatalf("twin lineup: %+v", got)
	}
	if _, ok := pool.FeaturedByGacha[491]; ok {
		t.Fatal("a twin without a regular summon got a lineup")
	}
}

// A twin without its own window (no notice) runs with its regular summon.
func TestPaidTwinWithoutAWindowRunsWithItsRegularSummon(t *testing.T) {
	regular := basicEntry(34)
	regular.StartDatetime, regular.EndDatetime = 5_000, 9_000 // already moved by the calendar
	file := summonRulesFile{New: []newSummon{{Id: 35, Asset: "limited_35", Pair: 34, Steps: []ruleStep{{Draws: 10, Price: 3000, Cur: "paid", Limit: 5}}}}}
	got := addNewSummons([]store.GachaCatalogEntry{regular}, file, 1_000)
	if len(got) != 2 || got[1].StartDatetime != 5_000 || got[1].EndDatetime != 9_000 {
		t.Fatalf("twin dates: %+v", got)
	}
	// Without a regular summon there is nothing to run with: not added.
	file.New[0].Pair = 99
	if got := addNewSummons([]store.GachaCatalogEntry{regular}, file, 0); len(got) != 1 {
		t.Fatalf("a twin without dates or a regular summon was added: %+v", got)
	}
}

// A summon paid with a specific ticket (★★★★ Premium Summon Ticket, 1006).
func TestTicketSummon(t *testing.T) {
	file := summonRulesFile{New: []newSummon{{Id: 970001, Asset: "confirm_ssr", Start: 1, End: 2,
		Steps: []ruleStep{{Draws: 1, Price: 1, Cur: "ticket", Ticket: 1006, Guar: "r4"}}}}}
	got := addNewSummons(nil, file, 0)
	if len(got) != 1 {
		t.Fatalf("entries: %+v", got)
	}
	// Always open, so listed after the summons of the day.
	if got[0].SortOrder != ticketSummonSortOrder {
		t.Fatalf("ticket summon sort order %d", got[0].SortOrder)
	}
	p := got[0].PricePhases[0]
	if p.PriceType != model.PriceTypeConsumableItem || p.PriceId != 1006 || p.Price != 1 || p.DrawCount != 1 ||
		p.FixedRarityMin != model.RaritySSRare || p.FixedCount != 1 {
		t.Fatalf("ticket draw: %+v", p)
	}
}

// With the calendar off every summon in the game data is open (1999-2099);
// the added summons are too, and a twin always runs with its regular summon.
func TestNewSummonsFollowTheCalendarMode(t *testing.T) {
	regular := basicEntry(489)
	regular.StartDatetime, regular.EndDatetime = 946598400000, 4102444799000
	file := summonRulesFile{New: []newSummon{
		{Id: 490, Asset: "limited_490", Pair: 489, Start: 1_680_000_000_000, End: 1_681_000_000_000, Steps: []ruleStep{{Draws: 10, Price: 3000, Cur: "paid"}}},
		{Id: 124, Asset: "limited_124", Start: 1_640_998_800_000, End: 1_641_175_199_999, Steps: []ruleStep{{Draws: 10, Price: 0, Cur: "free"}}},
	}}
	off := addNewSummonsFor([]store.GachaCatalogEntry{regular}, file, 0, false)
	if off[1].StartDatetime != regular.StartDatetime || off[1].EndDatetime != regular.EndDatetime {
		t.Fatalf("twin with the calendar off: %d-%d", off[1].StartDatetime, off[1].EndDatetime)
	}
	if off[2].StartDatetime > 1_000_000_000_000 || off[2].EndDatetime < 4_000_000_000_000 {
		t.Fatalf("summon without a regular one, calendar off: %d-%d", off[2].StartDatetime, off[2].EndDatetime)
	}
	// Calendar on: the twin still runs with its (moved) regular summon; the other keeps its window, moved.
	regular.StartDatetime, regular.EndDatetime = 1_680_100_000_000+7000, 1_681_200_000_000+7000
	on := addNewSummonsFor([]store.GachaCatalogEntry{regular}, file, 7000, true)
	if on[1].StartDatetime != regular.StartDatetime || on[2].StartDatetime != 1_640_998_800_000+7000 {
		t.Fatalf("calendar on: twin %d, other %d", on[1].StartDatetime, on[2].StartDatetime)
	}
}

// Some summons' art has no panel (appeal/) in the client: only a banner, or
// an appeal_background like the chapter summons'. The festival style then
// draws an empty panel with no summon button; they use the normal style.
func TestPlainSummonsUseTheNormalStyle(t *testing.T) {
	file := summonRulesFile{New: []newSummon{
		{Id: 970003, Asset: "confirm_60005", Plain: true, Start: 1000, End: 2000, Steps: []ruleStep{{Draws: 1, Price: 1, Cur: "ticket", Ticket: 1205, Guar: "r4:fire"}}},
		{Id: 970001, Asset: "confirm_ssr", Start: 1000, End: 2000, Steps: []ruleStep{{Draws: 1, Price: 1, Cur: "ticket", Ticket: 1006, Guar: "r4"}}},
	}}
	byId := map[int32]store.GachaCatalogEntry{}
	for _, e := range addNewSummons(nil, file, 0) {
		byId[e.GachaId] = e
	}
	if e := byId[970003]; e.BannerAssetName != "confirm_60005" || e.GachaDecorationType != model.GachaDecorationNormal {
		t.Fatalf("plain summon: %q style %d", e.BannerAssetName, e.GachaDecorationType)
	}
	if e := byId[970001]; e.GachaDecorationType != model.GachaDecorationFestival {
		t.Fatalf("summon with a panel: style %d", e.GachaDecorationType)
	}
}

// A prize box (Mama's Dream) is the client's box summon: its screen is the
// box panel with the prizes' stock.
func TestPrizeBoxIsABoxSummon(t *testing.T) {
	file := summonRulesFile{New: []newSummon{{Id: 200001, Asset: "common_200001", Plain: true, Start: 1000, End: 2000,
		Steps:  []ruleStep{{Draws: 1, Price: 1, Cur: "ticket", Ticket: 6064}},
		Prizes: []Prize{{Name: "Gems", Type: 12, Qty: 100, Stock: 5}}}}}
	got := addNewSummons(nil, file, 0)
	if len(got) != 1 || got[0].GachaModeType != model.GachaModeBox || got[0].GachaLabelType != model.GachaLabelPremium {
		t.Fatalf("prize box: %+v", got)
	}
}

// A summon missing from the game data that reran an earlier one (the last
// weekly summons, 04-30-2023) takes that summon's shards and lineup but keeps
// its own dates.
func TestLineupFromAnEarlierSummon(t *testing.T) {
	weekly := basicEntry(10094)
	weekly.GachaMedalId, weekly.MedalConsumableItemId, weekly.CeilingCount = 61, 6100, 150
	weekly.StartDatetime, weekly.EndDatetime = 1_000, 2_000
	file := summonRulesFile{New: []newSummon{{Id: 10107, Asset: "limited_10094", Lineup: 10094, Start: 5_000, End: 6_000,
		Steps: []ruleStep{{Draws: 1, Price: 300, Cur: "gems"}, {Draws: 10, Price: 3000, Cur: "gems", Guar: "r3w"}}}}}
	var rerun store.GachaCatalogEntry
	for _, e := range addNewSummons([]store.GachaCatalogEntry{weekly}, file, 0) {
		if e.GachaId == 10107 {
			rerun = e
		}
	}
	if rerun.StartDatetime != 5_000 || rerun.EndDatetime != 6_000 || rerun.GachaMedalId != 61 || rerun.MedalConsumableItemId != 6100 || rerun.CeilingCount != 150 {
		t.Fatalf("rerun: %+v", rerun)
	}
	pool := &GachaCatalog{FeaturedByGacha: map[int32]FeaturedSet{10094: {Costumes: []GachaPoolItem{{PossessionId: 34001}}}}}
	pool.applyNewFeatured(file)
	if fs := pool.FeaturedByGacha[10107]; len(fs.Costumes) != 1 || fs.Costumes[0].PossessionId != 34001 {
		t.Fatalf("rerun lineup: %+v", fs)
	}
}
