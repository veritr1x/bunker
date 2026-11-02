package masterdata

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"log"
	"sort"
	"sync"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// Event summons: each story event's box summon on the Summons screen's Event
// tab, drawn with the tickets its quests drop. The game data has the events,
// their tickets and a summon id per level (340001, 340002, ...; art
// event_340_01, ...), but not what the boxes held: the client fetched that
// from the game's web API. summon_events.json holds each level's main prizes
// as an event guide lists them where it does, else the event's weapons and
// Advanced Handbooks, and filler and odds after the one box on record (the
// JP Variation: Aurora Dynast, 2021). All of an event's ticket tiers draw from
// one box.
//
//go:embed summon_events.json
var eventSummonsJSON []byte

// BoxPrize is one prize in an event summon level: what it gives (Count each),
// how many the level holds (Stock; 0 for the unlimited pool), and whether it
// is a main prize (shown on the level's page) and a target (drawing every
// target lets the player level up).
type BoxPrize struct {
	Type   int32 `json:"t"`
	Id     int32 `json:"id"`
	Count  int32 `json:"n"`
	Stock  int32 `json:"stock"`
	Target bool  `json:"target"`
	Main   bool  `json:"main"`
}

// EventLevel is one level's box: a draw takes one of its prizes with
// probability Chance (every remaining one alike), else an unlimited prize.
type EventLevel struct {
	Chance float64    `json:"chance"`
	Items  []BoxPrize `json:"items"`
}

// EventSummon is one event's summon: its levels in order; the last one
// replenishes once emptied.
type EventSummon struct {
	Chapter int32        `json:"chapter"`
	Base    int32        `json:"base"`
	Assets  []string     `json:"assets"`
	Tickets []int32      `json:"tickets"`
	Levels  []EventLevel `json:"levels"`
	Src     string       `json:"src"`
}

type eventSummonsFile struct {
	Unlimited []BoxPrize    `json:"unlimited"`
	Events    []EventSummon `json:"events"`
}

func loadEventSummonsFile() (eventSummonsFile, error) {
	var f eventSummonsFile
	if err := json.Unmarshal(eventSummonsJSON, &f); err != nil {
		return f, fmt.Errorf("summon_events.json: %w", err)
	}
	return f, nil
}

var eventSummons struct {
	sync.RWMutex
	file   eventSummonsFile
	byBase map[int32]int
	runs   map[int32][]eventRun // by summon id: the event's chapter rows
}

// eventRun is one run of an event: its chapter row (the first run's, or a
// copy the Original calendar adds for a rerun) and its dates.
type eventRun struct {
	chapter    int32
	start, end int64
}

// EventSummonRunAt is the event run open at nowMillis for an event summon (its
// chapter row, for To Quests) and whether one is; isEvent is false for other
// summons. A run stays open for the summons' grace after it ends.
func EventSummonRunAt(gachaId int32, nowMillis int64) (chapter int32, open, isEvent bool) {
	eventSummons.RLock()
	defer eventSummons.RUnlock()
	runs, isEvent := eventSummons.runs[gachaId]
	for _, r := range runs {
		if r.start <= nowMillis && nowMillis < r.end+eventSummonGrace {
			return r.chapter, true, true
		}
	}
	return 0, false, isEvent
}

func setEventSummons(f eventSummonsFile) {
	eventSummons.Lock()
	defer eventSummons.Unlock()
	eventSummons.file = f
	eventSummons.byBase = map[int32]int{}
	for i, e := range f.Events {
		eventSummons.byBase[e.Base] = i
	}
}

// EventSummonFor is the event summon a summon id belongs to, and the level the
// id stands for (1 for the event's own id).
func EventSummonFor(gachaId int32) (EventSummon, int32, bool) {
	eventSummons.RLock()
	defer eventSummons.RUnlock()
	for level := int32(1); level <= 9; level++ {
		if i, ok := eventSummons.byBase[gachaId-level+1]; ok {
			e := eventSummons.file.Events[i]
			if int(level) <= len(e.Levels) {
				return e, level, true
			}
			return EventSummon{}, 0, false
		}
	}
	return EventSummon{}, 0, false
}

// EventSummonRuns is an event summon's runs (start, end), in date order.
func EventSummonRuns(gachaId int32) [][2]int64 {
	eventSummons.RLock()
	defer eventSummons.RUnlock()
	out := make([][2]int64, 0, len(eventSummons.runs[gachaId]))
	for _, r := range eventSummons.runs[gachaId] {
		out = append(out, [2]int64{r.start, r.end})
	}
	return out
}

// EventSummonUnlimited is the unlimited prizes every event summon shares.
func EventSummonUnlimited() []BoxPrize {
	eventSummons.RLock()
	defer eventSummons.RUnlock()
	return eventSummons.file.Unlimited
}

// eventSummonGrace: the summons stay open this long after their event ends.
const eventSummonGrace = 2 * 24 * 60 * 60 * 1000

// chapterRunStep: the Original calendar gives an event's later runs chapter
// rows of their own, the chapter + n * chapterRunStep (android_calendar.py
// COPY_STEP).
const chapterRunStep = 10_000_000

// eventRuns is an event chapter's runs: its own row and the rows the Original
// calendar gives its later runs, in date order; and when the first opens and
// the last closes.
func eventRuns(chapters map[int32]EntityMEventQuestChapter, chapter int32) (runs []eventRun, start, end int64, ok bool) {
	for id, c := range chapters {
		if id%chapterRunStep != chapter {
			continue
		}
		runs = append(runs, eventRun{chapter: id, start: c.StartDatetime, end: c.EndDatetime})
		if !ok || c.StartDatetime < start {
			start = c.StartDatetime
		}
		if !ok || c.EndDatetime > end {
			end = c.EndDatetime
		}
		ok = true
	}
	sort.Slice(runs, func(i, j int) bool { return runs[i].start < runs[j].start })
	return runs, start, end, ok
}

// AddEventSummons adds each event's summon for its event's dates (as the game
// data has them, so the Original calendar moves them with the event).
func AddEventSummons(entries []store.GachaCatalogEntry) []store.GachaCatalogEntry {
	f, err := loadEventSummonsFile()
	if err != nil {
		log.Printf("event summons off: %v", err)
		return entries
	}
	rows, err := utils.ReadTable[EntityMEventQuestChapter]("m_event_quest_chapter")
	if err != nil {
		log.Printf("event summons off: m_event_quest_chapter: %v", err)
		return entries
	}
	chapters := make(map[int32]EntityMEventQuestChapter, len(rows))
	for _, c := range rows {
		chapters[c.EventQuestChapterId] = c
	}
	setEventSummons(f)
	before := len(entries)
	entries = addEventSummons(entries, f, chapters)
	log.Printf("event summons: %d events", len(entries)-before)
	return entries
}

func addEventSummons(entries []store.GachaCatalogEntry, f eventSummonsFile, chapters map[int32]EntityMEventQuestChapter) []store.GachaCatalogEntry {
	taken := map[int32]bool{}
	for _, e := range entries {
		taken[e.GachaId] = true
	}
	allRuns := map[int32][]eventRun{}
	defer func() {
		eventSummons.Lock()
		eventSummons.runs = allRuns
		eventSummons.Unlock()
	}()
	for _, ev := range f.Events {
		if _, ok := chapters[ev.Chapter]; !ok || taken[ev.Base] || len(ev.Levels) == 0 || len(ev.Tickets) == 0 {
			continue
		}
		runs, start, end, _ := eventRuns(chapters, ev.Chapter)
		allRuns[ev.Base] = runs
		e := store.GachaCatalogEntry{
			GachaId:             ev.Base,
			GachaLabelType:      model.GachaLabelEvent,
			GachaModeType:       model.GachaModeBox,
			GachaAutoResetType:  model.GachaAutoResetNone,
			IsUserGachaUnlock:   true,
			StartDatetime:       start,
			EndDatetime:         end + eventSummonGrace,
			GachaDecorationType: model.GachaDecorationNormal,
			SortOrder:           ev.Chapter,
			BannerAssetName:     ev.Assets[0],
			GroupId:             ev.Base,
			// Listed only while a run is on, and To Quests opens that run
			// (service: bunkerGachaUnlockedFor, eventSummonLink).
			UnlockConditionType:        model.GachaUnlockEventRun,
			RelatedEventQuestChapterId: ev.Chapter,
		}
		phase := int32(1)
		for _, ticket := range ev.Tickets {
			for _, draws := range []int32{1, 10} {
				e.PricePhases = append(e.PricePhases, store.GachaPricePhaseEntry{
					PhaseId:      ev.Base*model.PhaseIdMultiplier + phase,
					PriceType:    model.PriceTypeConsumableItem,
					PriceId:      ticket,
					Price:        draws,
					RegularPrice: draws,
					DrawCount:    draws,
				})
				phase++
			}
		}
		entries = append(entries, e)
	}
	return entries
}

// SetEventSummonsForTest replaces the event summons (tests of other packages).
func SetEventSummonsForTest(events []EventSummon, unlimited []BoxPrize) {
	setEventSummons(eventSummonsFile{Events: events, Unlimited: unlimited})
}

// SetEventSummonRunsForTest sets an event summon's runs: chapter row -> start, end.
func SetEventSummonRunsForTest(gachaId int32, runs map[int32][2]int64) {
	eventSummons.Lock()
	defer eventSummons.Unlock()
	if eventSummons.runs == nil {
		eventSummons.runs = map[int32][]eventRun{}
	}
	var rs []eventRun
	for chapter, w := range runs {
		rs = append(rs, eventRun{chapter: chapter, start: w[0], end: w[1]})
	}
	sort.Slice(rs, func(i, j int) bool { return rs[i].start < rs[j].start })
	eventSummons.runs[gachaId] = rs
}
