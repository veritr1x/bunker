package service

import (
	"database/sql"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/missions"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// archiveLocalText stands in for the Archive's English text and its other
// languages (text_local) until the test ends.
func archiveLocalText(t *testing.T, english map[string]string, local map[string]map[string]string) {
	t.Helper()
	dir := t.TempDir()
	db, err := sql.Open("sqlite", filepath.Join(dir, "archive.db"))
	if err != nil {
		t.Fatal(err)
	}
	db.Exec(`CREATE TABLE text (key TEXT PRIMARY KEY, value TEXT)`)
	db.Exec(`CREATE TABLE text_local (lang TEXT, key TEXT, value TEXT, PRIMARY KEY(lang, key))`)
	for k, v := range english {
		db.Exec(`INSERT INTO text VALUES (?, ?)`, k, v)
	}
	for lang, text := range local {
		for k, v := range text {
			db.Exec(`INSERT INTO text_local VALUES (?, ?, ?)`, lang, k, v)
		}
	}
	db.Close()
	saved := archivePaths
	archivePaths = []string{filepath.Join(dir, "archive.db")}
	t.Cleanup(func() { archivePaths = saved })
}

func TestPanelLanguageFromTheRequest(t *testing.T) {
	for in, want := range map[string]string{"Japanese": "ja", "ja": "ja", "ja-JP": "ja", "Korean": "ko", "ko": "ko",
		"English": "en", "en": "en", "": "en", "French": "en"} {
		if got := panelLanguage(in); got != want {
			t.Errorf("panelLanguage(%q) = %q, want %q", in, got, want)
		}
	}
}

// A panel's title is a mission's: the game's own text in the page's language,
// matched by its English wording, with the panel's own numbers.
func TestPanelTitleInTheGamesLanguage(t *testing.T) {
	archiveLocalText(t, map[string]string{
		"mission.name.7": "Tap Mama 5 Times",
		"mission.name.8": "Clear a quest 1 time",
		"mission.name.9": "Clear Chapter 2 Quest 10 on Hard",
	}, map[string]map[string]string{"ja": {
		"mission.name.7": "ママを5回タップする",
		"mission.name.8": "クエストを1回クリアする",
		"mission.name.9": "2章クエスト10のハードをクリアする",
	}})
	text := openGameTextIn("ja")
	defer text.close()
	for en, want := range map[string]string{
		"Clear a quest 1 time":             "クエストを1回クリアする",       // the same wording
		"Tap Mama 10 Times":                "ママを10回タップする",        // another number
		"Clear Chapter 3 Quest 10 on Hard": "3章クエスト10のハードをクリアする", // only the changed number moves
		"Use 100 stamina":                  "Use 100 stamina",    // no mission says it: English
	} {
		if got := text.missionText(en); got != want {
			t.Errorf("%q: %q, want %q", en, got, want)
		}
	}
	english := openGameText()
	defer english.close()
	if got := english.missionText("Tap Mama 10 Times"); got != "Tap Mama 10 Times" {
		t.Fatalf("English page: %q", got)
	}
}

// An Archive built before other languages were indexed still names things in English.
func TestOlderArchiveNamesInEnglish(t *testing.T) {
	archiveText(t, map[string]string{"material.name.1": "Iron", "mission.name.7": "Tap Mama 5 Times"})
	text := openGameTextIn("ja")
	defer text.close()
	if got := text.text("material.name.1"); got != "Iron" {
		t.Fatalf("name: %q", got)
	}
	if got := text.missionText("Tap Mama 10 Times"); got != "Tap Mama 10 Times" {
		t.Fatalf("title: %q", got)
	}
}

// The page asks in its language (commonRequest.language): panel titles and
// reward names come back in it.
func TestPanelMissionWebAPIInJapanese(t *testing.T) {
	archiveLocalText(t, map[string]string{"mission.name.7": "Tap Mama 5 Times", "material.name.1": "Iron"},
		map[string]map[string]string{"ja": {"mission.name.7": "ママを5回タップする", "material.name.1": "鉄"}})
	users := &panelMemUsers{u: store.UserState{UserId: 1}}
	users.u.EnsureMaps()
	users.u.Ext.EnsureMaps()
	defer func(p func() *missions.Panels, u panelUserStore, n func() int64, s func(*missions.Panels, missions.PanelRun, int32, string) string) {
		panelSheets, panelUsers, panelNow, panelStoryText = p, u, n, s
	}(panelSheets, panelUsers, panelNow, panelStoryText)
	panelSheets, panelUsers, panelNow = testPanels, users, func() int64 { return 5000 }
	var storyLang string
	panelStoryText = func(_ *missions.Panels, _ missions.PanelRun, _ int32, lang string) string {
		storyLang = lang
		return ""
	}
	for lang, want := range map[string]string{"Japanese": "ママを10回タップする", "English": "Tap Mama 10 Times"} {
		common := map[string]any{"userIdString": "1", "sessionKey": "x", "language": lang}
		code, res := postJSON(t, "/127-web.0.0.1/api/wm/panel_mission/pages", map[string]any{"commonRequest": common, "webviewMissionId": "8"})
		if code != 200 {
			t.Fatalf("%s pages: %d %v", lang, code, res)
		}
		if got := dig(res["data"], "pages", 0, "panels", 0, "title"); got != want {
			t.Errorf("%s title: %#v, want %q", lang, got, want)
		}
		if got := dig(res["data"], "pages", 0, "panels", 0, "longTitle"); got != want {
			t.Errorf("%s long title: %#v, want %q", lang, got, want)
		}
		if wantLang := panelLanguage(lang); storyLang != wantLang {
			t.Errorf("%s story asked in %q", lang, storyLang)
		}
	}
	text := openGameTextIn("ja")
	defer text.close()
	if got := possessionName(text, int32(model.PossessionTypeMaterial), 1); got != "鉄" {
		t.Fatalf("reward name: %q", got)
	}
}

// The sheet's title and its completion story come from the master data in
// the page's language; the Japanese master has only Japanese, which an
// English page shows rather than nothing.
func TestPanelTitleAndStoryFromTheMaster(t *testing.T) {
	loadMaster(t)
	missionsRows, _ := utils.ReadTable[masterdata.EntityMWebviewMission]("m_webview_mission")
	titles, _ := utils.ReadTable[masterdata.EntityMWebviewMissionTitleText]("m_webview_mission_title_text")
	stars := int32(0)
	for _, m := range missionsRows {
		if m.TitleTextId == 1 {
			stars = m.WebviewMissionId
			break
		}
	}
	if stars == 0 {
		t.Skip("no webview mission titled 1")
	}
	hasEnglish := false
	for _, r := range titles {
		hasEnglish = hasEnglish || r.LanguageType == 2
	}
	run := missions.PanelRun{Id: stars}
	if got := panelTitle(run, "ja", "Anecdote: Stars"); got != "挿話：星" {
		t.Fatalf("Japanese title: %q", got)
	}
	if got := panelTitle(run, "en", "Anecdote: Stars"); got != "Anecdote: Stars" {
		t.Fatalf("English title: %q", got)
	}
	if hasEnglish {
		if got := panelTitle(run, "ko", "Anecdote: Stars"); got != "삽화: 별" {
			t.Fatalf("Korean title: %q", got)
		}
	}
	if got := panelTitle(missions.PanelRun{Id: -1}, "ja", "Anecdote: Stars"); got != "Anecdote: Stars" {
		t.Fatalf("unknown run: %q", got)
	}
	flavor, _ := utils.ReadTable[masterdata.EntityMWebviewPanelMissionCompleteFlavorText]("m_webview_panel_mission_complete_flavor_text")
	stories := map[int32]map[int32]string{}
	for _, r := range flavor {
		if stories[r.WebviewPanelMissionCompleteFlavorTextId] == nil {
			stories[r.WebviewPanelMissionCompleteFlavorTextId] = map[int32]string{}
		}
		stories[r.WebviewPanelMissionCompleteFlavorTextId][r.LanguageType] = r.CompleteFlavorText
	}
	first := stories[101]
	if first == nil {
		t.Skip("no story 101")
	}
	if got := flavorIn(stories[101], "ja"); got != first[1] {
		t.Fatalf("Japanese story: %q", got)
	}
	want := first[2]
	if want == "" {
		want = first[1] // the Japanese master
	}
	if got := flavorIn(stories[101], "en"); got != want || !strings.Contains(got, "\n") {
		t.Fatalf("English story: %q", got)
	}
}

// Gems are named by the game's own word for them (gem.name), and "Gems"
// before there is an Archive.
func TestGemsInTheGamesLanguage(t *testing.T) {
	archiveLocalText(t, map[string]string{"gem.name": "Gems"}, map[string]map[string]string{"ja": {"gem.name": "ジェム"}})
	text := openGameTextIn("ja")
	defer text.close()
	if got := possessionName(text, int32(model.PossessionTypeFreeGem), 0); got != "ジェム" {
		t.Fatalf("Japanese: %q", got)
	}
	none := &gameText{lang: "ja"}
	if got := possessionName(none, int32(model.PossessionTypePaidGem), 0); got != "Gems" {
		t.Fatalf("without an Archive: %q", got)
	}
}
