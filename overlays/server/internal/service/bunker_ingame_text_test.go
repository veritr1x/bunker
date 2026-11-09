package service

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/internal/bunkertext"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/missions"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// activePack makes pack the active language pack until the test ends.
func activePack(t *testing.T, pack map[string]any) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "active.json")
	data, _ := json.Marshal(pack)
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
	bunkertext.SetActive(path)
	t.Cleanup(func() { bunkertext.SetActive("") })
}

func ptBR(bunker, game, master map[string]any) map[string]any {
	return map[string]any{"format": 1, "language": "pt-BR", "name": "Português (Brasil)", "bunker": bunker, "game": game, "master": master}
}

// The notices' tabs, labels and messages follow the pack on an English client; the notices
// themselves (recovered from the live service) stay as they were written.
func TestNoticesInThePacksLanguage(t *testing.T) {
	activePack(t, ptBR(map[string]any{
		"ingame.notices.tab.news":        "Notícias",
		"ingame.notices.badge.summons":   "Invocações",
		"ingame.notices.postscript":      "[P.S.: {date}]",
		"ingame.notices.summons_details": "Detalhes",
		"ingame.notices.unavailable":     "Este aviso não está disponível.",
		"ingame.notices.badge.issue":     "Problema",
	}, nil, nil))
	h := NewNotices(writeNoticePack(t), func() int64 { return 5_000 })
	_, list, _ := getNotice(t, h, "/en/information/")
	for _, want := range []string{`<html lang="pt-BR">`, ">Notícias<", ">Problema<", "[P.S.: <time", ">Events<", "Known issues"} {
		if !strings.Contains(list, want) {
			t.Fatalf("list lacks %q:\n%s", want, list)
		}
	}
	_, detail, _ := getNotice(t, h, "/en/information/?informationId=10")
	if !strings.Contains(detail, ">Invocações<") || !strings.Contains(detail, ">Detalhes</a>") || !strings.Contains(detail, "Abstract Savior Summons On Now") {
		t.Fatalf("detail:\n%s", detail)
	}
	_, missing, _ := getNotice(t, h, "/en/information/?informationId=999")
	if !strings.Contains(missing, "Este aviso não está disponível.") {
		t.Fatalf("missing notice:\n%s", missing)
	}
	// A Japanese client: the pack replaces English only.
	_, ja, _ := getNotice(t, h, "/ja/information/")
	if strings.Contains(ja, "Notícias") || !strings.Contains(ja, ">News<") {
		t.Fatalf("Japanese client:\n%s", ja)
	}
}

func TestSummonDetailsInThePacksLanguage(t *testing.T) {
	activePack(t, ptBR(map[string]any{
		"ingame.summons.period_open_ticket": "Desde {start} (UTC) · sem data de fim: aberta enquanto você tiver um bilhete",
		"ingame.summons.gems.one":           "{n} gema",
		"ingame.summons.gems.other":         "{n} gemas",
		"ingame.summons.items":              "{n} × {item}",
		"ingame.summons.ticket":             "Bilhete de Invocação",
		"ingame.summons.free":               "Grátis",
	}, nil, nil))
	w := bunkertext.For("en")
	ticket := store.GachaCatalogEntry{StartDatetime: 1627437600000, EndDatetime: 4102444799000}
	if got := periodHTML(w, ticket, true); got != "<p class=k>Desde 2021/07/28 (UTC) · sem data de fim: aberta enquanto você tiver um bilhete</p>" {
		t.Fatalf("period: %s", got)
	}
	text := openGameText()
	defer text.close()
	for _, c := range []struct {
		p    store.GachaPricePhaseEntry
		want string
	}{
		{store.GachaPricePhaseEntry{Price: 3000, PriceType: model.PriceTypeGem}, "3.000 gemas"},
		{store.GachaPricePhaseEntry{Price: 0, PriceType: model.PriceTypeGem}, "Grátis"},
		{store.GachaPricePhaseEntry{Price: 1, PriceType: model.PriceTypeGem}, "1 gema"},
		// paid gems untranslated: the English, its number written the pack's way
		{store.GachaPricePhaseEntry{Price: 1200, PriceType: model.PriceTypePaidGem}, "1.200 paid gems"},
	} {
		if got := text.price(c.p); got != c.want {
			t.Errorf("price %+v: %q, want %q", c.p, got, c.want)
		}
	}
	if got := text.rate(12.5); got != "12,500%" {
		t.Errorf("rate: %q", got)
	}
}

// Names of the game's things come from the pack's game text on an English client, else the Archive's English.
func TestGameNamesFromThePack(t *testing.T) {
	archiveText(t, map[string]string{"material.name.1": "Iron", "material.name.2": "Copper",
		"mission.name.7": "Tap Mama 5 Times"})
	activePack(t, ptBR(nil, map[string]any{"material.name.1": "Ferro", "mission.name.7": "Toque na Mamãe 5 vezes"}, nil))
	text := openGameText()
	defer text.close()
	if got := text.text("material.name.1"); got != "Ferro" {
		t.Errorf("translated name: %q", got)
	}
	if got := text.text("material.name.2"); got != "Copper" {
		t.Errorf("untranslated name: %q", got)
	}
	if got := text.missionText("Tap Mama 10 Times"); got != "Toque na Mamãe 10 vezes" {
		t.Errorf("mission: %q", got)
	}
	ja := openGameTextIn("ja")
	defer ja.close()
	if got := ja.text("material.name.1"); got != "Iron" {
		t.Errorf("Japanese client: %q", got)
	}
}

// Bunker's own panel sheet page speaks the pack.
func TestPanelSheetInThePacksLanguage(t *testing.T) {
	activePack(t, ptBR(map[string]any{"ingame.panels.sheet": "Folha {page}", "ingame.panels.close": "Fechar"},
		map[string]any{"mission.name.7": "Toque na Mamãe 5 vezes"}, nil))
	archiveText(t, map[string]string{"mission.name.7": "Tap Mama 5 Times"})
	users := &panelMemUsers{u: store.UserState{UserId: 1}}
	users.u.EnsureMaps()
	users.u.Ext.EnsureMaps()
	defer func(p func() *missions.Panels, u panelUserStore, n func() int64) {
		panelSheets, panelUsers, panelNow = p, u, n
	}(panelSheets, panelUsers, panelNow)
	panelSheets, panelUsers, panelNow = testPanels, users, func() int64 { return 5000 }
	body := serve(t, "GET", "/web/en/panelmission/8?userId=1", nil).Body.String()
	for _, want := range []string{`<html lang="pt-BR">`, "Folha 1", ">Fechar</a>", "Toque na Mamãe 10 vezes"} {
		if !strings.Contains(body, want) {
			t.Fatalf("page lacks %q:\n%s", want, body)
		}
	}
}

// A panel's title and story on an English client: the pack's master text for the row, else English.
func TestPanelTitleFromThePacksMaster(t *testing.T) {
	loadMaster(t)
	missionsRows, _ := utils.ReadTable[masterdata.EntityMWebviewMission]("m_webview_mission")
	var run missions.PanelRun
	for _, m := range missionsRows {
		if m.TitleTextId == 1 {
			run.Id = m.WebviewMissionId
			break
		}
	}
	if run.Id == 0 {
		t.Skip("no webview mission titled 1")
	}
	activePack(t, ptBR(nil, nil, map[string]any{"m_webview_mission_title_text.1": "Episódio: Estrelas",
		"m_webview_panel_mission_complete_flavor_text.101": "Uma história."}))
	if got := panelTitle(run, "en", "Anecdote: Stars"); got != "Episódio: Estrelas" {
		t.Fatalf("title: %q", got)
	}
	if got := panelTitle(run, "ja", "Anecdote: Stars"); got != "挿話：星" {
		t.Fatalf("Japanese title: %q", got)
	}
	if got := storyFor(101, map[int32]string{2: "A story."}, "en"); got != "Uma história." {
		t.Fatalf("story: %q", got)
	}
	if got := storyFor(102, map[int32]string{2: "Another."}, "en"); got != "Another." {
		t.Fatalf("untranslated story: %q", got)
	}
}
