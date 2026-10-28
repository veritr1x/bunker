package missions

import (
	"testing"

	pb "lunar-tear/server/gen/proto"
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
