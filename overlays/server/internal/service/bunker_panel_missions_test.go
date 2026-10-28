package service

import (
	"encoding/json"
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
		Words:    []string{"She", "Will"},
		Parts:    testParts(),
	}}}
	return missions.NewPanels(map[int32]*missions.PanelSheets{8: sheet},
		[]missions.PanelRun{{Id: 8, Mission: 8, Target: 8, Start: 1000, End: 9000}}, map[[2]int32]int32{{8, 1}: 15})
}

// testParts: piece 1 starts at the bottom-right corner, turned over.
func testParts() [][4]int32 {
	parts := make([][4]int32, 45)
	for i := range parts {
		parts[i] = [4]int32{int32(9 - i%9), int32(5 - i/9), 180 * int32(1-i%2), int32(i % 2)}
	}
	return parts
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

	// The game asks for /web/<language>/panelmission/{sheet}.
	if !IsPanelMissionPath("/web/en/panelmission/8") || !IsPanelMissionPath("/web/en/panelmission/8/claim") ||
		!IsPanelMissionPath("/panelmission/8") || IsPanelMissionPath("/information/") {
		t.Fatal("path matching")
	}
	page := serve(t, "GET", "/web/en/panelmission/8?userId=1&playerId=1&sessionKey=x&appVersion=3.7.1", nil)
	body := page.Body.String()
	for _, want := range []string{"Anecdote: Doll", "Tap Mama 10 Times", "10 / 10", "4 / 10", `action="/web/en/panelmission/8/claim?`,
		`href="uniwebview://panelmission?close=1"`} { // the game closes its web view on a close message (no Back key on iOS)
		if !strings.Contains(body, want) {
			t.Fatalf("page lacks %q:\n%s", want, body)
		}
	}
	claim := func(panel string) *httptest.ResponseRecorder {
		return serve(t, "POST", "/web/en/panelmission/8/claim?userId=1", url.Values{"page": {"1"}, "panel": {panel}})
	}
	if w := claim("0"); w.Code != http.StatusSeeOther || w.Header().Get("Location") != "/web/en/panelmission/8?userId=1" {
		t.Fatalf("claim: %d %q", w.Code, w.Header().Get("Location"))
	}
	if n := len(users.u.Gifts.NotReceived); n != 1 {
		t.Fatalf("%d gifts after one claim", n)
	}
	if text := users.u.Gifts.NotReceived[0].GiftCommon.DescriptionGiftTextId; text != 25 {
		t.Fatalf("gift text %d, want 25 (Earned from panel missions.)", text)
	}
	claim("0") // again: nothing more
	claim("1") // not reached: nothing
	if n := len(users.u.Gifts.NotReceived); n != 1 {
		t.Fatalf("%d gifts after a repeat and an unreached claim", n)
	}
}

func postJSON(t *testing.T, target string, body any) (int, map[string]any) {
	t.Helper()
	b, _ := json.Marshal(body)
	r := httptest.NewRequest("POST", target, strings.NewReader(string(b)))
	r.Header.Set("Content-Type", "application/json; charset=utf-8")
	w := httptest.NewRecorder()
	ServePanelMission(w, r)
	var out map[string]any
	json.Unmarshal(w.Body.Bytes(), &out)
	return w.Code, out
}

func dig(v any, path ...any) any {
	for _, p := range path {
		switch k := p.(type) {
		case string:
			v = v.(map[string]any)[k]
		case int:
			v = v.([]any)[k]
		}
	}
	return v
}

// The official panel mission page (served from the notice pack) asks the
// server for the sheets and receives panels through its own API.
func TestPanelMissionWebAPI(t *testing.T) {
	users := &panelMemUsers{u: store.UserState{UserId: 1}}
	users.u.EnsureMaps()
	users.u.Ext.EnsureMaps()
	users.u.Ext.PanelMissions[8] = store.PanelMissionState{Progress: map[int32]int64{100: 10, 101: 4}}
	defer func(p func() *missions.Panels, u panelUserStore, n func() int64, s func(*missions.Panels, missions.PanelRun, int32) string) {
		panelSheets, panelUsers, panelNow, panelStoryText = p, u, n, s
	}(panelSheets, panelUsers, panelNow, panelStoryText)
	panelSheets, panelUsers, panelNow = testPanels, users, func() int64 { return 5000 }
	panelStoryText = func(*missions.Panels, missions.PanelRun, int32) string {
		return "She fights.\nShe channels quiet will into her blade."
	}
	common := map[string]any{"userIdString": "1", "sessionKey": "x"}

	// The page's route parameter is a string.
	code, res := postJSON(t, "/127-web.0.0.1/api/wm/panel_mission/pages", map[string]any{"commonRequest": common, "webviewMissionId": "8"})
	if code != 200 {
		t.Fatalf("pages: %d %v", code, res)
	}
	data := res["data"]
	for _, c := range []struct {
		path []any
		want any
	}{
		{[]any{"webviewMissionId"}, 8.0},
		{[]any{"webviewPanelMissionId"}, 8.0},
		{[]any{"eventTitle"}, "Anecdote: Doll"},
		{[]any{"startDate"}, 1000.0},
		{[]any{"endDate"}, 9000.0},
		{[]any{"isAllComplete"}, false},
		{[]any{"pages", 0, "isComplete"}, false},
		{[]any{"pages", 0, "isTermOver"}, false},
		{[]any{"pages", 0, "imageFileName"}, panelFile("card_full.jpg")},
		{[]any{"pages", 0, "compFlavorText"}, "<span>She</span> fights. She channels quiet <span>will</span> into her blade."},
		{[]any{"pages", 0, "bgParts", 0, "bgPartsIndex"}, 1.0},
		{[]any{"pages", 0, "bgParts", 0, "imagePath"}, panelFile("card_parts_01.jpg")},
		{[]any{"pages", 0, "bgParts", 0, "transform", "moveBeforeX"}, 9.0},
		{[]any{"pages", 0, "bgParts", 0, "transform", "moveBeforeY"}, 5.0},
		{[]any{"pages", 0, "bgParts", 0, "transform", "rotate"}, 180.0},
		{[]any{"pages", 0, "panels", 0, "positionId"}, 1.0},
		{[]any{"pages", 0, "panels", 0, "title"}, "Tap Mama 10 Times"},
		{[]any{"pages", 0, "panels", 0, "flavorText"}, "She"},
		{[]any{"pages", 0, "panels", 0, "panelMissionProgressStatusType"}, 2.0},
		{[]any{"pages", 0, "panels", 0, "numerator"}, 10.0},
		{[]any{"pages", 0, "panels", 0, "denominator"}, 10.0},
		{[]any{"pages", 0, "panels", 0, "reward", "rewardType"}, 5.0},
		{[]any{"pages", 0, "panels", 0, "reward", "rewardCount"}, 2180.0},
		{[]any{"pages", 0, "panels", 0, "reward", "rewardImageFileName"}, "100004.png"},
		{[]any{"pages", 0, "panels", 1, "panelMissionProgressStatusType"}, 1.0},
		{[]any{"pages", 0, "panels", 1, "numerator"}, 4.0},
	} {
		if got := dig(data, c.path...); got != c.want {
			t.Fatalf("%v = %#v, want %#v", c.path, got, c.want)
		}
	}
	if n := len(dig(data, "pages", 0, "bgParts").([]any)); n != 45 {
		t.Fatalf("%d background parts", n)
	}

	claim := func(position int) (int, map[string]any) {
		return postJSON(t, "/127-web.0.0.1/api/wm/panel_mission/panel/reward", map[string]any{"commonRequest": common,
			"webviewMissionId": 8, "webviewPanelMissionId": 8, "page": 1, "panelGroupId": 15, "positionId": position})
	}
	code, res = claim(1)
	if code != 200 || dig(res, "data", "reward", "rewardCount") != 2180.0 || dig(res, "data", "isComplete") != false {
		t.Fatalf("receive: %d %v", code, res)
	}
	if g := users.u.Gifts.NotReceived; len(g) != 1 || g[0].GiftCommon.DescriptionGiftTextId != 25 {
		t.Fatalf("gifts: %+v", g)
	}
	if code, _ = claim(1); code == 200 {
		t.Fatal("a panel paid twice")
	}
	if code, _ = claim(2); code == 200 {
		t.Fatal("paid a panel not reached")
	}
	// The page's last panel: the page is complete and pays its own reward too.
	st := users.u.Ext.PanelMissions[8]
	st.Progress[101] = 10
	code, res = claim(2)
	if code != 200 || dig(res, "data", "isComplete") != true || dig(res, "data", "pageData", "rewardList", 0, "rewardCount") != 300.0 ||
		dig(res, "data", "pageData", "imageFileName") != panelFile("card_full.jpg") {
		t.Fatalf("last panel: %d %v", code, res)
	}
	_, res = postJSON(t, "/127-web.0.0.1/api/wm/panel_mission/pages", map[string]any{"commonRequest": common, "webviewMissionId": "8"})
	if dig(res, "data", "isAllComplete") != true || dig(res, "data", "pages", 0, "panels", 0, "panelMissionProgressStatusType") != 3.0 {
		t.Fatalf("after completing: %v", res)
	}
}

// With the notice pack's web app, the game's page is the official one.
func TestPanelMissionServesTheOfficialPage(t *testing.T) {
	defer func(w panelWebApp) { panelWeb = w }(panelWeb)
	panelWeb = NewNotices(writeWebPack(t), func() int64 { return 10 })
	defer func(p func() *missions.Panels, u panelUserStore) { panelSheets, panelUsers = p, u }(panelSheets, panelUsers)
	panelSheets, panelUsers = testPanels, &panelMemUsers{u: store.UserState{UserId: 1}}
	page := serve(t, "GET", "/web/en/panelmission/8?userId=1&serverAddress=127.0.0.1", nil)
	if !strings.Contains(page.Body.String(), "NieR Re[in]carnation") {
		t.Fatalf("not the official page: %s", page.Body.String())
	}
}
