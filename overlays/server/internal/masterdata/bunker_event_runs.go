package masterdata

import (
	_ "embed"
	"encoding/json"
	"log"
	"strconv"
	"sync"
)

// Bunker: a rerun event's earlier runs as they were (scripts/event_runs.py,
// event_runs.json). Each run had its own medal: its quests dropped it and its
// quest bonuses paid it. The final game data keeps the last run's drops and
// bonuses only. The Original calendar replays each run as a chapter copy
// (chapter + n * COPY_STEP) and gives the copy of an earlier run its own link
// (the run's link + (RunIds + n) * COPY_STEP, android_calendar.event_runs), so
// a chapter carrying that link is that run: the server pays the run's drops and
// bonuses. With the calendar off the chapter keeps the final link and nothing
// changes.

//go:embed event_runs.json
var eventRunsJSON []byte

const RunIds = 100

type EventRunBonusRule struct {
	Kind       string // "character", "costume" or "weapon"
	Id         int32  // CharacterId, CostumeId or WeaponId
	LimitBreak int32  // the lowest limit break count it takes (costume, weapon)
	Pays       [][3]int32
}

type EventRun struct {
	Link    int32
	Drops   map[int32][][3]int32 // quest -> [possession type, id, count]
	bonus   map[int32]string
	bonuses map[string][]EventRunBonusRule
}

// BonusRules is a quest's bonus payouts in this run (nil: none).
func (r *EventRun) BonusRules(questId int32) []EventRunBonusRule {
	return r.bonuses[r.bonus[questId]]
}

type EventRunTable struct {
	step int32
	runs map[int32][]*EventRun // base chapter -> runs in order, the last nil
}

// For is the run a chapter is, given the link the active game data gives it; nil when
// it is the final game data's (no run data, the last run, or the calendar off).
func (t *EventRunTable) For(chapterId, chapterLink int32) *EventRun {
	if t == nil || t.step == 0 {
		return nil
	}
	n := chapterId / t.step
	runs := t.runs[chapterId%t.step]
	if int(n) >= len(runs) || runs[n] == nil {
		return nil
	}
	if chapterLink != runs[n].Link+(RunIds+n)*t.step {
		return nil
	}
	return runs[n]
}

type rawEventRun struct {
	Link    int32                        `json:"link"`
	Drops   map[string][][3]int32        `json:"drops"`
	Bonus   map[string]string            `json:"bonus"`
	Bonuses map[string][]json.RawMessage `json:"bonuses"`
}

func ParseEventRuns(data []byte) (*EventRunTable, error) {
	var raw struct {
		CopyStep int32                     `json:"copy_step"`
		Chapters map[string][]*rawEventRun `json:"chapters"`
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}
	t := &EventRunTable{step: raw.CopyStep, runs: map[int32][]*EventRun{}}
	for key, runs := range raw.Chapters {
		chapter, err := strconv.Atoi(key)
		if err != nil {
			return nil, err
		}
		out := make([]*EventRun, len(runs))
		for i, r := range runs {
			if r == nil {
				continue
			}
			run := &EventRun{Link: r.Link, Drops: map[int32][][3]int32{}, bonus: map[int32]string{}, bonuses: map[string][]EventRunBonusRule{}}
			for q, d := range r.Drops {
				id, _ := strconv.Atoi(q)
				run.Drops[int32(id)] = d
			}
			for q, b := range r.Bonus {
				id, _ := strconv.Atoi(q)
				run.bonus[int32(id)] = b
			}
			for name, rules := range r.Bonuses {
				for _, rawRule := range rules {
					var parts []json.RawMessage
					var rule EventRunBonusRule
					if err := json.Unmarshal(rawRule, &parts); err != nil || len(parts) != 4 {
						return nil, err
					}
					if err := json.Unmarshal(parts[0], &rule.Kind); err != nil {
						return nil, err
					}
					if err := json.Unmarshal(parts[1], &rule.Id); err != nil {
						return nil, err
					}
					if err := json.Unmarshal(parts[2], &rule.LimitBreak); err != nil {
						return nil, err
					}
					if err := json.Unmarshal(parts[3], &rule.Pays); err != nil {
						return nil, err
					}
					run.bonuses[name] = append(run.bonuses[name], rule)
				}
			}
			out[i] = run
		}
		t.runs[int32(chapter)] = out
	}
	return t, nil
}

var (
	eventRunsOnce  sync.Once
	eventRunsTable *EventRunTable
)

// EventRuns is the shipped run data (event_runs.json).
func EventRuns() *EventRunTable {
	eventRunsOnce.Do(func() {
		t, err := ParseEventRuns(eventRunsJSON)
		if err != nil {
			log.Printf("event_runs.json: %v", err)
			return
		}
		eventRunsTable = t
	})
	return eventRunsTable
}
