package masterdata

import (
	"reflect"
	"strings"
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

func testEventFile() eventSummonsFile {
	return eventSummonsFile{
		Unlimited: []BoxPrize{{Type: 5, Id: 100002, Count: 1}},
		Events: []EventSummon{{
			Chapter: 340, Base: 340001, Assets: []string{"event_340_01", "event_340_02"}, Tickets: []int32{6071},
			Levels: []EventLevel{
				{Chance: 0.35, Items: []BoxPrize{{Type: 2, Id: 330731, Count: 1, Stock: 1, Target: true, Main: true}, {Type: 6, Id: 1, Count: 1000, Stock: 30}}},
				{Chance: 0.30, Items: []BoxPrize{{Type: 6, Id: 1, Count: 5000, Stock: 50, Main: true}}},
			},
		}},
	}
}

// Each event's summon is one Event-tab box summon on the Summons screen,
// open from the event's start until two days after it ends (the notices: the
// Event Summons can be used until two days after the event period ends),
// drawn with any of its tickets, one or ten at a time.
func TestEventSummonsJoinTheCatalog(t *testing.T) {
	chapters := map[int32]EntityMEventQuestChapter{340: {EventQuestChapterId: 340, StartDatetime: 1_000_000, EndDatetime: 2_000_000}}
	got := addEventSummons(nil, testEventFile(), chapters)
	if len(got) != 1 {
		t.Fatalf("%d entries", len(got))
	}
	e := got[0]
	if e.GachaId != 340001 || e.GachaLabelType != model.GachaLabelEvent || e.GachaModeType != model.GachaModeBox || e.GroupId != 340001 ||
		e.BannerAssetName != "event_340_01" || e.StartDatetime != 1_000_000 || e.EndDatetime != 2_000_000+2*24*3600*1000 {
		t.Fatalf("event summon: %+v", e)
	}
	if len(e.PricePhases) != 2 || e.PricePhases[0].PriceType != model.PriceTypeConsumableItem || e.PricePhases[0].PriceId != 6071 ||
		e.PricePhases[0].DrawCount != 1 || e.PricePhases[1].DrawCount != 10 || e.PricePhases[1].Price != 10 {
		t.Fatalf("event summon prices: %+v", e.PricePhases)
	}
}

// The Original calendar gives an event's later runs chapter rows of their own
// (the chapter + n * 10,000,000; android_calendar.py COPY_STEP). The summon
// stays open from the first run to two days after the last, so tickets from
// a rerun can be spent (chapters 300 and 301 rerun in 2023).
func TestEventSummonsOpenForEveryRun(t *testing.T) {
	chapters := map[int32]EntityMEventQuestChapter{
		340:            {EventQuestChapterId: 340, StartDatetime: 1_000_000, EndDatetime: 2_000_000},
		340 + 10000000: {EventQuestChapterId: 340 + 10000000, StartDatetime: 9_000_000, EndDatetime: 9_500_000},
		341:            {EventQuestChapterId: 341, StartDatetime: 50_000_000, EndDatetime: 60_000_000},
	}
	got := addEventSummons(nil, testEventFile(), chapters)
	if len(got) != 1 || got[0].StartDatetime != 1_000_000 || got[0].EndDatetime != 9_500_000+2*24*3600*1000 {
		t.Fatalf("event summon: %+v", got)
	}
}

// Its levels have ids of their own (340001, 340002, ...), all one summon.
func TestEventSummonLevelIds(t *testing.T) {
	setEventSummons(testEventFile())
	defer setEventSummons(eventSummonsFile{})
	for id, want := range map[int32]int32{340001: 1, 340002: 2} {
		box, level, ok := EventSummonFor(id)
		if !ok || box.Base != 340001 || level != want {
			t.Fatalf("%d: level %d ok %v", id, level, ok)
		}
	}
	if _, _, ok := EventSummonFor(340003); ok {
		t.Fatal("a level past the last one")
	}
	if _, _, ok := EventSummonFor(store.GachaCatalogEntry{}.GachaId); ok {
		t.Fatal("id 0")
	}
}

// The embedded file is the compiled data and holds every event.
func TestEmbeddedEventSummonsAreValid(t *testing.T) {
	f, err := loadEventSummonsFile()
	if err != nil {
		t.Fatal(err)
	}
	if len(f.Events) < 30 || len(f.Unlimited) == 0 {
		t.Fatalf("%d events, %d unlimited", len(f.Events), len(f.Unlimited))
	}
	for _, e := range f.Events {
		if len(e.Levels) != len(e.Assets) || len(e.Tickets) == 0 {
			t.Fatalf("event %d: %d levels, %d assets, tickets %v", e.Chapter, len(e.Levels), len(e.Assets), e.Tickets)
		}
		last := e.Levels[len(e.Levels)-1]
		for _, it := range last.Items {
			if it.Target {
				t.Fatalf("event %d: the last level replenishes; it has no main-prize targets", e.Chapter)
			}
		}
		for i, l := range e.Levels[:len(e.Levels)-1] {
			targets := 0
			for _, it := range l.Items {
				if it.Target {
					targets++
				}
			}
			if targets == 0 {
				t.Fatalf("event %d level %d has nothing to level up with", e.Chapter, i+1)
			}
		}
	}
}

// Between runs the summon is closed, and To Quests opens the run that is on
// (its chapter row): the first run's row is closed during a rerun, and the
// game then fell back to its first event tab.
func TestEventSummonFollowsTheOpenRun(t *testing.T) {
	chapters := map[int32]EntityMEventQuestChapter{
		340:            {EventQuestChapterId: 340, StartDatetime: 1_000_000, EndDatetime: 2_000_000},
		340 + 10000000: {EventQuestChapterId: 340 + 10000000, StartDatetime: 900_000_000, EndDatetime: 950_000_000},
	}
	got := addEventSummons(nil, testEventFile(), chapters)
	if len(got) != 1 || got[0].UnlockConditionType != model.GachaUnlockEventRun {
		t.Fatalf("event summon: %+v", got)
	}
	grace := int64(2 * 24 * 3600 * 1000)
	for _, c := range []struct {
		now     int64
		chapter int32
		open    bool
	}{
		{1_500_000, 340, true},
		{2_000_000 + grace - 1, 340, true},
		{500_000_000, 0, false},
		{920_000_000, 340 + 10000000, true},
		{960_000_000 + grace, 0, false},
	} {
		chapter, open, isEvent := EventSummonRunAt(340001, c.now)
		if !isEvent || open != c.open || chapter != c.chapter {
			t.Errorf("at %d: chapter %d open %v (event %v), want %d %v", c.now, chapter, open, isEvent, c.chapter, c.open)
		}
	}
	if _, _, isEvent := EventSummonRunAt(999, 1_500_000); isEvent {
		t.Error("another summon counted as an event summon")
	}
}

func TestEventLevelsGetListedPrizes(t *testing.T) {
	const x, y, z, u, q = 1, 2, 3, 4, 5
	in := eventSummonsFile{
		Unlimited: []BoxPrize{{Type: 5, Id: u, Count: 1}},
		Events: []EventSummon{{Base: 900, Levels: []EventLevel{
			{Chance: 0.35, Items: []BoxPrize{{Type: 5, Id: x, Count: 2, Stock: 5}}},
			{Chance: 0.30},
		}}},
	}
	got := withListedPrizes(in, map[int32][]int32{900: {x, y}, 901: {u, z}, 777: {q}}, map[int32]int32{x: 10, y: 20, z: 40, u: 10, q: 10})
	// The box and its stock stay as they were (the pace to the targets with
	// them); the listed materials join the level's unlimited draws.
	if !reflect.DeepEqual(got.Events[0].Levels[0].Items, in.Events[0].Levels[0].Items) || len(got.Events[0].Levels[1].Items) != 0 {
		t.Fatalf("boxes changed: %+v", got.Events[0].Levels)
	}
	if want := []BoxPrize{{Type: 5, Id: y, Count: 1, Weight: 6}}; !reflect.DeepEqual(got.Events[0].Levels[0].Unlimited, want) {
		t.Fatalf("level 1 unlimited %+v", got.Events[0].Levels[0].Unlimited)
	}
	if want := []BoxPrize{{Type: 5, Id: z, Count: 1, Weight: 1}}; !reflect.DeepEqual(got.Events[0].Levels[1].Unlimited, want) {
		t.Fatalf("level 2 unlimited %+v", got.Events[0].Levels[1].Unlimited)
	}
	if len(in.Events[0].Levels[0].Unlimited) != 0 || len(in.Events[0].Levels[1].Unlimited) != 0 {
		t.Fatalf("the input was changed: %+v", in.Events[0].Levels)
	}
}

// Every material the game lists for an event summon level ("2/<asset>/..."
// routes, route id = the level's summon id) is in that level's box, its
// unlimited draws or the shared unlimited pool.
func TestEventSummonsHoldTheirListedItemsOnTheGameData(t *testing.T) {
	loadTestMaster(t)
	f, err := loadEventSummonsFile()
	if err != nil {
		t.Fatal(err)
	}
	f = withListedPrizes(f, eventSummonListed(), materialRarity())
	has := map[int32]map[int32]bool{}
	unlimited := map[int32]bool{}
	for _, p := range f.Unlimited {
		unlimited[p.Id] = true
	}
	for _, e := range f.Events {
		for i, l := range e.Levels {
			m := map[int32]bool{}
			for _, p := range append(append([]BoxPrize(nil), l.Items...), l.Unlimited...) {
				m[p.Id] = true
			}
			has[e.Base+int32(i)] = m
		}
	}
	routes, _ := utils.ReadTable[EntityMPossessionAcquisitionRoute]("m_possession_acquisition_route")
	listed, missing := 0, 0
	for _, r := range routes {
		if r.AcquisitionRouteType != 3 || !strings.HasPrefix(r.RelationValue, "2/") || r.PossessionType != 5 {
			continue
		}
		listed++
		if !has[r.RouteId][r.PossessionId] && !unlimited[r.PossessionId] {
			if missing++; missing <= 5 {
				t.Errorf("summon %d lacks material %d", r.RouteId, r.PossessionId)
			}
		}
	}
	if listed == 0 || missing != 0 {
		t.Fatalf("%d listed, %d missing", listed, missing)
	}
}

// An event that ran twice with different summons (the Original calendar's
// copy row for the rerun): each summon is open for its own run only.
func TestEventSummonForOneRun(t *testing.T) {
	chapters := map[int32]EntityMEventQuestChapter{
		340:            {EventQuestChapterId: 340, StartDatetime: 1_000_000, EndDatetime: 2_000_000},
		340 + 10000000: {EventQuestChapterId: 340 + 10000000, StartDatetime: 900_000_000, EndDatetime: 950_000_000},
	}
	f := testEventFile()
	second := f.Events[0]
	second.Base, second.Run = 350001, 2
	f.Events[0].Run = 1
	f.Events = append(f.Events, second)
	got := addEventSummons(nil, f, chapters)
	grace := int64(2 * 24 * 3600 * 1000)
	if len(got) != 2 || got[0].StartDatetime != 1_000_000 || got[0].EndDatetime != 2_000_000+grace ||
		got[1].StartDatetime != 900_000_000 || got[1].EndDatetime != 950_000_000+grace {
		t.Fatalf("summons: %+v", got)
	}
	if _, open, _ := EventSummonRunAt(340001, 920_000_000); open {
		t.Error("the first run's summon is open in the rerun")
	}
	if chapter, open, _ := EventSummonRunAt(350001, 920_000_000); !open || chapter != 340+10000000 {
		t.Errorf("the rerun's summon: chapter %d open %v", chapter, open)
	}
	if _, open, _ := EventSummonRunAt(350001, 1_500_000); open {
		t.Error("the rerun's summon is open in the first run")
	}
	// A run the calendar doesn't have: no summon.
	f.Events[1].Run = 3
	if got := addEventSummons(nil, f, chapters); len(got) != 1 {
		t.Fatalf("summon for a missing run: %+v", got)
	}
}

// A summon added partway through its event (Vol. 2, Vol. 3) opens that many
// days after each run starts and closes with the event.
func TestEventSummonOpensDaysIntoTheRun(t *testing.T) {
	const day = int64(24 * 3600 * 1000)
	chapters := map[int32]EntityMEventQuestChapter{340: {EventQuestChapterId: 340, StartDatetime: 10 * day, EndDatetime: 40 * day}}
	f := testEventFile()
	f.Events[0].OpensDays = 7
	got := addEventSummons(nil, f, chapters)
	if len(got) != 1 || got[0].StartDatetime != 17*day || got[0].EndDatetime != 42*day {
		t.Fatalf("summon: %+v", got)
	}
	if _, open, _ := EventSummonRunAt(340001, 16*day); open {
		t.Error("open before its day")
	}
	if chapter, open, _ := EventSummonRunAt(340001, 17*day); !open || chapter != 340 {
		t.Errorf("on its day: chapter %d open %v", chapter, open)
	}
}

// A summon fed by several quest chapters (the once-per-day quests that drop
// the Crossover Commemoration tickets) is open across all of them.
func TestEventSummonFollowsSeveralChapters(t *testing.T) {
	chapters := map[int32]EntityMEventQuestChapter{
		400030: {EventQuestChapterId: 400030, StartDatetime: 1_000, EndDatetime: 2_000},
		400031: {EventQuestChapterId: 400031, StartDatetime: 2_000, EndDatetime: 3_000},
		400032: {EventQuestChapterId: 400032, StartDatetime: 3_000, EndDatetime: 4_000},
	}
	f := testEventFile()
	f.Events[0].Chapter, f.Events[0].Chapters = 400030, []int32{400031, 400032}
	got := addEventSummons(nil, f, chapters)
	if len(got) != 1 || got[0].StartDatetime != 1_000 || got[0].EndDatetime != 4_000+2*24*3600*1000 {
		t.Fatalf("summon: %+v", got)
	}
	if chapter, open, _ := EventSummonRunAt(340001, 3_500); !open || chapter != 400032 {
		t.Errorf("in the third chapter: chapter %d open %v", chapter, open)
	}
}

// The summons the first version left out: a second summon for an event's
// first run or rerun, the Vol. 2 and Vol. 3 summons added partway through an
// event, and the Crossover Commemoration summons. Each is on the game data's
// chapters, with tickets the game has.
func TestEventSummonsCoverEveryEventArtSet(t *testing.T) {
	loadTestMaster(t)
	f, err := loadEventSummonsFile()
	if err != nil {
		t.Fatal(err)
	}
	chapterRows, _ := utils.ReadTable[EntityMEventQuestChapter]("m_event_quest_chapter")
	chapters := map[int32]bool{}
	for _, c := range chapterRows {
		chapters[c.EventQuestChapterId] = true
	}
	items, _ := utils.ReadTable[EntityMConsumableItem]("m_consumable_item")
	tickets := map[int32]bool{}
	for _, i := range items {
		tickets[i.ConsumableItemId] = true
	}
	byBase := map[int32]EventSummon{}
	for _, e := range f.Events {
		byBase[e.Base] = e
		for _, c := range append([]int32{e.Chapter}, e.Chapters...) {
			if !chapters[c] {
				t.Errorf("summon %d: chapter %d is not in the game data", e.Base, c)
			}
		}
		for _, id := range e.Tickets {
			if !tickets[id] {
				t.Errorf("summon %d: ticket %d is not in the game data", e.Base, id)
			}
		}
	}
	for base, want := range map[int32]struct {
		chapter   int32
		run, days int32
		levels    int
	}{
		301001: {301, 1, 0, 7}, 331001: {301, 2, 0, 7},
		317001: {317, 1, 0, 7}, 319001: {317, 1, 7, 4}, 324001: {317, 2, 0, 7},
		320001: {400030, 0, 0, 1}, 326001: {400048, 0, 0, 1},
		334001: {333, 0, 7, 5}, 335001: {333, 0, 14, 5}, 338001: {337, 0, 14, 5},
	} {
		e, ok := byBase[base]
		if !ok {
			t.Errorf("summon %d is missing", base)
			continue
		}
		if e.Chapter != want.chapter || e.Run != want.run || e.OpensDays != want.days || len(e.Levels) != want.levels {
			t.Errorf("summon %d: chapter %d run %d opens day %d, %d levels; want %+v", base, e.Chapter, e.Run, e.OpensDays, len(e.Levels), want)
		}
	}
}
