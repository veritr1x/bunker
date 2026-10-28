package service

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"lunar-tear/server/internal/missions"
	"lunar-tear/server/internal/store"
)

type panelMemUsers struct{ u store.UserState }

func (m *panelMemUsers) LoadUser(int64) (store.UserState, error) { return m.u, nil }
func (m *panelMemUsers) UpdateUser(_ int64, f func(*store.UserState)) (store.UserState, error) {
	f(&m.u)
	return m.u, nil
}

func testPanels() *missions.Panels {
	sheet := &missions.PanelSheets{Name: "Anecdote: Doll", Pages: []missions.PanelPage{{
		Page: 1,
		Panels: []missions.Panel{
			{Text: "Tap Mama 10 Times", Rule: missions.Rule{Kind: "mama_tap"}, N: 10, Rewards: []missions.PanelReward{{Type: 5, Id: 100004, Count: 2180}}},
			{Text: "Defeat 10 bosses", Rule: missions.Rule{Kind: "defeat_boss"}, N: 10, Rewards: []missions.PanelReward{{Type: 5, Id: 401002, Count: 300}}},
		},
		Complete: []missions.PanelReward{{Type: 12, Id: 0, Count: 300}},
	}}}
	return missions.NewPanels(map[int32]*missions.PanelSheets{8: sheet},
		[]missions.PanelRun{{Id: 8, Mission: 8, Target: 8, Start: 1000, End: 9000}}, map[[2]int32]int32{{8, 1}: 15})
}

func serve(t *testing.T, method, target string, form url.Values) *httptest.ResponseRecorder {
	t.Helper()
	var body *strings.Reader
	if form != nil {
		body = strings.NewReader(form.Encode())
	} else {
		body = strings.NewReader("")
	}
	r := httptest.NewRequest(method, target, body)
	if form != nil {
		r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	}
	w := httptest.NewRecorder()
	ServePanelMission(w, r)
	return w
}

// The game's page for an Anecdote run shows its panels with the player's
// progress; a reached panel's reward goes to the gift box, once.
func TestPanelMissionPage(t *testing.T) {
	users := &panelMemUsers{u: store.UserState{UserId: 1}}
	users.u.EnsureMaps()
	users.u.Ext.EnsureMaps()
	users.u.Ext.PanelMissions[8] = store.PanelMissionState{Progress: map[int32]int64{100: 10, 101: 4}}
	defer func(p func() *missions.Panels, u panelUserStore, n func() int64) {
		panelSheets, panelUsers, panelNow = p, u, n
	}(panelSheets, panelUsers, panelNow)
	panelSheets, panelUsers, panelNow = testPanels, users, func() int64 { return 5000 }

	if !IsPanelMissionPath("/panelmission/8") || !IsPanelMissionPath("/panelmission/8/claim") || IsPanelMissionPath("/information/") {
		t.Fatal("path matching")
	}
	page := serve(t, "GET", "/panelmission/8?userId=1&playerId=1&sessionKey=x&appVersion=3.7.1", nil)
	body := page.Body.String()
	for _, want := range []string{"Anecdote: Doll", "Tap Mama 10 Times", "10 / 10", "4 / 10"} {
		if !strings.Contains(body, want) {
			t.Fatalf("page lacks %q:\n%s", want, body)
		}
	}
	claim := func(panel string) int {
		return serve(t, "POST", "/panelmission/8/claim?userId=1", url.Values{"page": {"1"}, "panel": {panel}}).Code
	}
	if code := claim("0"); code != http.StatusSeeOther {
		t.Fatalf("claim: %d", code)
	}
	if n := len(users.u.Gifts.NotReceived); n != 1 {
		t.Fatalf("%d gifts after one claim", n)
	}
	claim("0") // again: nothing more
	claim("1") // not reached: nothing
	if n := len(users.u.Gifts.NotReceived); n != 1 {
		t.Fatalf("%d gifts after a repeat and an unreached claim", n)
	}
}
