package missions

import (
	_ "embed"
	"encoding/json"
	"errors"
	"log"
	"sort"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// Anecdotes were web panel missions: each page a sheet of panels ("Clear a
// dungeon 10 times: XL Weapon Enhancement x100") whose web page and data lived
// on the old web server. panel_missions.json, from scripts/gen_panel_missions.py,
// holds each sheet with every panel as a mission rule; a run of an Anecdote
// counts what the player does while it is open, and the sheet's web page
// (service/bunker_panel_missions.go) pays a panel once it is reached and the
// page's own reward once every panel is. A completed page unlocks its story
// in the Library.

//go:embed panel_missions.json
var panelJSON []byte

// panelRunStep: the Original calendar's copies of a run (android_calendar.py COPY_STEP).
const panelRunStep = 10_000_000

type PanelReward struct {
	Type  int32 `json:"t"`
	Id    int32 `json:"id"`
	Count int32 `json:"n"`
}

type Panel struct {
	Text    string        `json:"text"`
	Rule    Rule          `json:"rule"`
	N       int64         `json:"n"`
	Standin bool          `json:"standin"` // the sources don't record the exact condition; the nearest Bunker counts
	Rewards []PanelReward `json:"rewards"`
}

type PanelPage struct {
	Page     int32         `json:"page"`
	Panels   []Panel       `json:"panels"`
	Complete []PanelReward `json:"complete"`
	Words    []string      `json:"words"` // each panel's word, shown where it opens and in bold in the story
	// The card's 45 pieces (9 x 5, row by row) as the sheet scatters them:
	// column and row (from 1), rotation in degrees, and which of the two
	// moves brings it home.
	Parts [][4]int32 `json:"parts"`
}

type PanelSheets struct {
	Name   string      `json:"name"`
	Source string      `json:"source"`
	Pages  []PanelPage `json:"pages"`
}

// PanelRun is one run of an Anecdote: its web panel mission (a copy per run)
// and the panel mission (sheet) the game's page asks for.
type PanelRun struct {
	Id, Mission, Target int32
	Start, End          int64
}

type Panels struct {
	Sheets   map[int32]*PanelSheets // by Anecdote (the first run's web panel mission)
	Runs     []PanelRun
	byTarget map[int32]PanelRun
	pageIds  map[[2]int32]int32 // (sheet, page) -> WebviewPanelMissionPageId
}

func loadPanelSheets() (map[int32]*PanelSheets, error) {
	var f struct {
		Parts    [][4]int32             `json:"parts"` // every sheet scatters the pieces alike
		Missions map[int32]*PanelSheets `json:"missions"`
	}
	if err := json.Unmarshal(panelJSON, &f); err != nil {
		return nil, err
	}
	for _, s := range f.Missions {
		for i := range s.Pages {
			if s.Pages[i].Parts == nil {
				s.Pages[i].Parts = f.Parts
			}
		}
	}
	return f.Missions, nil
}

func loadPanels() *Panels {
	sheets, err := loadPanelSheets()
	if err != nil {
		log.Printf("panel missions off: %v", err)
		sheets = nil
	}
	return buildPanels(sheets, read[masterdata.EntityMWebviewMission]("m_webview_mission"),
		read[masterdata.EntityMWebviewPanelMission]("m_webview_panel_mission"))
}

// panelLibrarySlot: with the Original calendar, the row an Anecdote with
// several runs is listed by in the Library (android_calendar.py LIBRARY_SLOT);
// it spans all the runs and isn't one.
const panelLibrarySlot = 99

func buildPanels(sheets map[int32]*PanelSheets, missions []masterdata.EntityMWebviewMission, pages []masterdata.EntityMWebviewPanelMission) *Panels {
	p := &Panels{Sheets: sheets, byTarget: map[int32]PanelRun{}, pageIds: map[[2]int32]int32{}}
	for _, m := range missions {
		run := PanelRun{Id: m.WebviewMissionId, Mission: m.WebviewMissionId % panelRunStep, Target: m.WebviewMissionTargetId,
			Start: m.StartDatetime, End: m.EndDatetime}
		if sheets[run.Mission] == nil || m.WebviewMissionId/panelRunStep == panelLibrarySlot {
			continue
		}
		p.Runs = append(p.Runs, run)
		p.byTarget[run.Target] = run
	}
	sort.Slice(p.Runs, func(i, j int) bool { return p.Runs[i].Start < p.Runs[j].Start })
	for _, pm := range pages {
		p.pageIds[[2]int32{pm.WebviewPanelMissionId, pm.Page}] = pm.WebviewPanelMissionPageId
	}
	return p
}

// runFor is an Anecdote's first run, for tests.
func (p *Panels) runFor(mission int32) *PanelRun {
	for i := range p.Runs {
		if p.Runs[i].Mission == mission {
			return &p.Runs[i]
		}
	}
	return nil
}

// Run is the run whose sheet the game's page asks for (/panelmission/{target})
// at now: the game's banners always open an Anecdote's first sheet, so while a
// later run of that Anecdote (a copy) is open, it is that run.
func (p *Panels) Run(target int32, now int64) (PanelRun, bool) {
	r, ok := p.byTarget[target]
	if !ok && target/panelRunStep == panelLibrarySlot { // the Anecdote's Library row: its first run, or the one on now
		r, ok = p.byTarget[target%panelRunStep]
	}
	if !ok || r.open(now) {
		return r, ok
	}
	for _, o := range p.Runs {
		if o.Mission == r.Mission && o.open(now) {
			return o, true
		}
	}
	return r, true
}

func (r PanelRun) open(now int64) bool { return now >= r.Start && (r.End == 0 || now < r.End) }

func ensure(st store.PanelMissionState) store.PanelMissionState {
	if st.Progress == nil {
		st.Progress = map[int32]int64{}
	}
	if st.Claimed == nil {
		st.Claimed = map[int32]bool{}
	}
	if st.PageDone == nil {
		st.PageDone = map[int32]int64{}
	}
	return st
}

// track counts one request towards the panels of the runs open now.
func (cat *Catalog) trackPanels(after *store.UserState, c *counts, now int64) {
	p := cat.Panels
	if p == nil {
		return
	}
	for _, run := range p.Runs {
		if !run.open(now) {
			continue
		}
		st := ensure(after.Ext.PanelMissions[run.Id])
		changed := false
		for _, pg := range p.Sheets[run.Mission].Pages {
			for i, panel := range pg.Panels {
				key := pg.Page*100 + int32(i)
				if st.Claimed[key] || st.Progress[key] >= panel.N {
					continue
				}
				m := &Mission{Rule: panel.Rule}
				v := st.Progress[key]
				if stateKinds[panel.Rule.Kind] {
					v = max(v, cat.stateValue(m, after))
				} else {
					v += cat.amountFor(m, c)
				}
				if v = min(v, panel.N); v != st.Progress[key] {
					st.Progress[key] = v
					changed = true
				}
			}
		}
		if changed {
			after.Ext.PanelMissions[run.Id] = st
		}
	}
}

var (
	ErrNoPanel      = errors.New("no such panel")
	ErrNotReached   = errors.New("the panel is not reached yet")
	ErrClaimed      = errors.New("the panel's reward was already received")
	ErrRunNotActive = errors.New("the Anecdote is not open")
)

// Claim pays a reached panel of a run's sheet (by the sheet the game asks for)
// once, and the page's own reward when it is the page's last panel. It returns
// what to grant; the caller grants it.
func (p *Panels) Claim(u *store.UserState, target, page, index int32, now int64) ([]PanelReward, error) {
	run, ok := p.Run(target, now)
	if !ok {
		return nil, ErrNoPanel
	}
	if !run.open(now) {
		return nil, ErrRunNotActive
	}
	var pg *PanelPage
	for i := range p.Sheets[run.Mission].Pages {
		if p.Sheets[run.Mission].Pages[i].Page == page {
			pg = &p.Sheets[run.Mission].Pages[i]
		}
	}
	if pg == nil || index < 0 || int(index) >= len(pg.Panels) {
		return nil, ErrNoPanel
	}
	u.Ext.EnsureMaps()
	st := ensure(u.Ext.PanelMissions[run.Id])
	key := page*100 + index
	switch {
	case st.Claimed[key]:
		return nil, ErrClaimed
	case st.Progress[key] < pg.Panels[index].N:
		return nil, ErrNotReached
	}
	st.Claimed[key] = true
	out := append([]PanelReward(nil), pg.Panels[index].Rewards...)
	all := true
	for i := range pg.Panels {
		all = all && st.Claimed[page*100+int32(i)]
	}
	if all && st.PageDone[page] == 0 {
		st.PageDone[page] = now
		out = append(out, pg.Complete...)
	}
	u.Ext.PanelMissions[run.Id] = st
	return out, nil
}

// PagesDone are the story pages the player completed in any run (page id ->
// first completion time), for the Library.
func (p *Panels) PagesDone(u *store.UserState) map[int32]int64 {
	out := map[int32]int64{}
	byId := map[int32]PanelRun{}
	for _, r := range p.Runs {
		byId[r.Id] = r
	}
	for runId, st := range u.Ext.PanelMissions {
		run, ok := byId[runId]
		if !ok {
			continue
		}
		for page, at := range st.PageDone {
			id := p.pageIds[[2]int32{run.Target, page}]
			if id != 0 && at != 0 && (out[id] == 0 || at < out[id]) {
				out[id] = at
			}
		}
	}
	return out
}

// NewPanels builds panel sheets from parts, for tests elsewhere.
func NewPanels(sheets map[int32]*PanelSheets, runs []PanelRun, pageIds map[[2]int32]int32) *Panels {
	p := &Panels{Sheets: sheets, Runs: runs, byTarget: map[int32]PanelRun{}, pageIds: pageIds}
	for _, r := range runs {
		p.byTarget[r.Target] = r
	}
	return p
}

// Progress is a run's sheet state for a player (empty if untouched).
func (p *Panels) Progress(u *store.UserState, run PanelRun) store.PanelMissionState {
	return ensure(u.Ext.PanelMissions[run.Id])
}

// PageId is a sheet page's WebviewPanelMissionPageId.
func (p *Panels) PageId(target, page int32) int32 { return p.pageIds[[2]int32{target, page}] }
