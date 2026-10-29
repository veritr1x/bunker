package missions

import (
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// The embedded sheets: eight Anecdotes, every panel counted by a rule and paying something.
func TestPanelSheetsAreComplete(t *testing.T) {
	sheets, err := loadPanelSheets()
	if err != nil {
		t.Fatal(err)
	}
	if len(sheets) != 8 {
		t.Fatalf("%d Anecdotes", len(sheets))
	}
	for id, s := range sheets {
		if len(s.Pages) != 2 {
			t.Errorf("Anecdote %d: %d pages", id, len(s.Pages))
		}
		for _, pg := range s.Pages {
			if len(pg.Words) != len(pg.Panels) || len(pg.Parts) != 45 {
				t.Errorf("Anecdote %d page %d: %d words for %d panels, %d pieces", id, pg.Page, len(pg.Words), len(pg.Panels), len(pg.Parts))
			}
			for i, p := range pg.Panels {
				if p.Rule.Kind == "" || p.N <= 0 || len(p.Rewards) == 0 {
					t.Errorf("Anecdote %d page %d panel %d: %+v", id, pg.Page, i, p)
				}
			}
		}
	}
}

// A run's panels count what the player does while it is open, and a panel's
// reward is paid once it is reached; the page's reward once every panel is.
func TestPanelRunCountsAndPays(t *testing.T) {
	cat, st, uid, _ := realSave(t)
	u, err := st.LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}
	u.Ext.EnsureMaps()
	doll := cat.Panels.runFor(8)
	if doll == nil {
		t.Fatal("no run of Anecdote: Doll")
	}
	during := doll.Start + 1000
	tap := func(at int64, n int32) {
		prev := store.CloneUserState(u)
		cat.Track(&prev, &u, "/apb.api.mission.MissionService/UpdateMissionProgress", &pb.UpdateMissionProgressRequest{
			CageMeasurableValues: &pb.CageMeasurableValues{MamaTappedCount: n},
		}, at)
	}
	key := mamaPanel(t, cat)
	tap(doll.Start-1000, 10) // before the run: nothing
	if got := u.Ext.PanelMissions[doll.Id].Progress[key]; got != 0 {
		t.Fatalf("counted before the run: %d", got)
	}
	tap(during, 4)
	tap(during, 9)
	if got := u.Ext.PanelMissions[doll.Id].Progress[key]; got != 10 {
		t.Fatalf("Tap Mama 10 times: progress %d, want 10 (capped)", got)
	}
	rewards, err := cat.Panels.Claim(&u, doll.Target, key/100, key%100, during)
	if err != nil || len(rewards) == 0 {
		t.Fatalf("claim: %v %v", rewards, err)
	}
	if again, err := cat.Panels.Claim(&u, doll.Target, key/100, key%100, during); err == nil || len(again) > 0 {
		t.Fatal("a panel paid twice")
	}
	// Every panel of the page reached and claimed: the page is done and pays its own reward.
	page := cat.Panels.Sheets[8].Pages[0]
	st8 := u.Ext.PanelMissions[doll.Id]
	for i, p := range page.Panels {
		st8.Progress[int32(page.Page)*100+int32(i)] = p.N
	}
	var last []PanelReward
	for i := range page.Panels {
		k := int32(page.Page)*100 + int32(i)
		if k == key {
			continue
		}
		if last, err = cat.Panels.Claim(&u, doll.Target, page.Page, int32(i), during); err != nil {
			t.Fatal(err)
		}
	}
	if u.Ext.PanelMissions[doll.Id].PageDone[page.Page] == 0 {
		t.Fatal("page not done with every panel claimed")
	}
	if len(last) < len(page.Panels[len(page.Panels)-1].Rewards)+len(page.Complete) {
		t.Fatalf("the last claim did not add the page reward: %v", last)
	}
	if done := cat.Panels.PagesDone(&u); len(done) == 0 {
		t.Fatal("no page done for the Library")
	}
}

func mamaPanel(t *testing.T, cat *Catalog) int32 {
	for _, pg := range cat.Panels.Sheets[8].Pages {
		for i, p := range pg.Panels {
			if p.Rule.Kind == "mama_tap" {
				return pg.Page*100 + int32(i)
			}
		}
	}
	t.Fatal("Anecdote: Doll has no Tap Mama panel")
	return 0
}

// The game's banners open an Anecdote's first sheet (/panelmission/8) in every
// run; the sheet is the run open now, a later run's copy.
func TestPanelSheetIsTheOpenRun(t *testing.T) {
	sheet := &PanelSheets{Name: "Anecdote: Doll", Pages: []PanelPage{{Page: 1, Panels: []Panel{
		{Text: "Tap Mama 10 Times", Rule: Rule{Kind: "mama_tap"}, N: 10, Rewards: []PanelReward{{Type: 12, Count: 50}}},
	}}}}
	third := 2*panelRunStep + 8
	p := NewPanels(map[int32]*PanelSheets{8: sheet}, []PanelRun{
		{Id: 8, Mission: 8, Target: 8, Start: 1000, End: 2000},
		{Id: int32(third), Mission: 8, Target: int32(third), Start: 5000, End: 9000},
	}, nil)
	if run, ok := p.Run(8, 6000); !ok || run.Id != int32(third) {
		t.Fatalf("sheet 8 during the third run: %+v %v", run, ok)
	}
	if run, ok := p.Run(8, 1500); !ok || run.Id != 8 {
		t.Fatalf("sheet 8 during the first run: %+v %v", run, ok)
	}
	if run, ok := p.Run(8, 3000); !ok || run.Id != 8 {
		t.Fatalf("sheet 8 between runs: %+v %v", run, ok)
	}
	u := store.UserState{}
	u.Ext.EnsureMaps()
	u.Ext.PanelMissions[int32(third)] = store.PanelMissionState{Progress: map[int32]int64{100: 10}}
	if rewards, err := p.Claim(&u, 8, 1, 0, 6000); err != nil || len(rewards) != 1 {
		t.Fatalf("claim on sheet 8 during the third run: %v %v", rewards, err)
	}
}

// Every panel pays an item the game has (its id, not its art's name).
func TestPanelRewardsAreGameItems(t *testing.T) {
	cat, _, _, _ := realSave(t)
	have := map[int32]map[int32]bool{2: {}, 3: {}, 5: {}, 6: {}}
	for _, r := range read[masterdata.EntityMWeapon]("m_weapon") {
		have[2][r.WeaponId] = true
	}
	for _, r := range read[masterdata.EntityMCompanion]("m_companion") {
		have[3][r.CompanionId] = true
	}
	for _, r := range read[masterdata.EntityMMaterial]("m_material") {
		have[5][r.MaterialId] = true
	}
	for _, r := range read[masterdata.EntityMConsumableItem]("m_consumable_item") {
		have[6][r.ConsumableItemId] = true
	}
	for id, s := range cat.Panels.Sheets {
		for _, pg := range s.Pages {
			rewards := append([]PanelReward(nil), pg.Complete...)
			for _, p := range pg.Panels {
				rewards = append(rewards, p.Rewards...)
			}
			for _, r := range rewards {
				if ids, ok := have[r.Type]; ok && !ids[r.Id] {
					t.Errorf("Anecdote %d page %d: no item %d/%d", id, pg.Page, r.Type, r.Id)
				}
			}
		}
	}
}

// With the Original calendar the Library lists an Anecdote by one row that
// spans all its runs (android_calendar.py library_missions); it isn't a run.
func TestPanelRunsSkipTheLibraryRow(t *testing.T) {
	sheets := map[int32]*PanelSheets{8: {Name: "Anecdote: Doll", Pages: []PanelPage{{Page: 1}}}}
	missions := []masterdata.EntityMWebviewMission{
		{WebviewMissionId: 8, WebviewMissionType: 2, WebviewMissionTargetId: 8, StartDatetime: 1000, EndDatetime: 2000},
		{WebviewMissionId: panelRunStep + 8, WebviewMissionType: 2, WebviewMissionTargetId: panelRunStep + 8, StartDatetime: 5000, EndDatetime: 9000},
		{WebviewMissionId: 99*panelRunStep + 8, WebviewMissionType: 1, WebviewMissionTargetId: 99*panelRunStep + 8, StartDatetime: 1000, EndDatetime: 9000},
	}
	p := buildPanels(sheets, missions, nil)
	if len(p.Runs) != 2 {
		t.Fatalf("runs: %+v", p.Runs)
	}
	if run, ok := p.Run(8, 3000); !ok || run.Id != 8 || run.open(3000) {
		t.Fatalf("between runs the sheet isn't open: %+v %v", run, ok)
	}
	if run, _ := p.Run(8, 6000); run.Id != panelRunStep+8 {
		t.Fatalf("second run: %+v", run)
	}
	// The game may open the sheet by the Library row: the run on now.
	if run, ok := p.Run(99*panelRunStep+8, 6000); !ok || run.Id != panelRunStep+8 {
		t.Fatalf("by the Library row: %+v %v", run, ok)
	}
	if run, ok := p.Run(99*panelRunStep+8, 3000); !ok || run.open(3000) {
		t.Fatalf("by the Library row between runs: %+v %v", run, ok)
	}
}
