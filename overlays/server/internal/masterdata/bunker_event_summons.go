package masterdata

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"log"
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
// as nierrein.guide lists them where it does, else the event's weapons and
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

// EventSummonUnlimited is the unlimited prizes every event summon shares.
func EventSummonUnlimited() []BoxPrize {
	eventSummons.RLock()
	defer eventSummons.RUnlock()
	return eventSummons.file.Unlimited
}

// eventSummonGrace: the summons stay open this long after their event ends.
const eventSummonGrace = 2 * 24 * 60 * 60 * 1000

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
	for _, ev := range f.Events {
		c, ok := chapters[ev.Chapter]
		if !ok || taken[ev.Base] || len(ev.Levels) == 0 || len(ev.Tickets) == 0 {
			continue
		}
		e := store.GachaCatalogEntry{
			GachaId:                    ev.Base,
			GachaLabelType:             model.GachaLabelEvent,
			GachaModeType:              model.GachaModeBox,
			GachaAutoResetType:         model.GachaAutoResetNone,
			IsUserGachaUnlock:          true,
			StartDatetime:              c.StartDatetime,
			EndDatetime:                c.EndDatetime + eventSummonGrace,
			GachaDecorationType:        model.GachaDecorationNormal,
			SortOrder:                  ev.Chapter,
			BannerAssetName:            ev.Assets[0],
			GroupId:                    ev.Base,
			UnlockConditionType:        model.GachaUnlockNone,
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
