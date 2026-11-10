package bunkertext

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"
)

// The cases every implementation of Bunker's text passes (bunker_text.py, BunkerText.java, LTText.m).
const sharedCases = "../../../android/tools/bunker_text_cases.json"

type sharedCase struct {
	Name        string            `json:"name"`
	Language    string            `json:"language"`
	Translation map[string]string `json:"translation"`
	Call        string            `json:"call"`
	Key         string            `json:"key"`
	Fallback    string            `json:"fallback"`
	N           int64             `json:"n"`
	Params      map[string]string `json:"params"`
	Expect      json.RawMessage   `json:"expect"`
}

func TestSharedCases(t *testing.T) {
	data, err := os.ReadFile(sharedCases)
	if err != nil {
		t.Fatal(err)
	}
	var file struct {
		English map[string]string `json:"english"`
		Cases   []sharedCase      `json:"cases"`
	}
	if err := json.Unmarshal(data, &file); err != nil {
		t.Fatal(err)
	}
	for _, c := range file.Cases {
		texts := newTexts(file.English, c.Language, c.Translation)
		var got any
		switch c.Call {
		case "t":
			got = texts.T(c.Key, c.Params)
		case "t_or":
			got = texts.TOr(c.Key, c.Fallback, c.Params)
		case "count":
			got = texts.Count(c.Key, c.N, c.Params)
		case "around":
			continue // pages only: the server puts no control inside a sentence
		default:
			t.Fatalf("%s: unknown call %s", c.Name, c.Call)
		}
		var want any
		json.Unmarshal(c.Expect, &want)
		if !reflect.DeepEqual(got, want) {
			t.Errorf("%s: got %q, want %q", c.Name, got, want)
		}
	}
}

func TestNumbers(t *testing.T) {
	for _, c := range []struct {
		lang string
		n    int64
		want string
	}{
		{"en", 1200, "1,200"}, {"de", 1200, "1.200"}, {"pt-BR", 1234567, "1.234.567"}, {"zh-Hans", 12000, "12,000"},
		{"es", 1200, "1200"}, {"es", 12000, "12.000"}, {"fr", 1200, "1 200"}, {"hi", 1234567, "12,34,567"},
		{"de-CH", 1200, "1'200"}, {"en", -1200, "-1,200"},
	} {
		if got := Number(c.lang, c.n); got != c.want {
			t.Errorf("Number(%s, %d) = %q, want %q", c.lang, c.n, got, c.want)
		}
	}
	if got := Decimal("pt-BR", 2.5, 3); got != "2,500" {
		t.Errorf("Decimal pt-BR = %q", got)
	}
	if got := Decimal("en", 1234.5, 3); got != "1,234.500" {
		t.Errorf("Decimal en = %q", got)
	}
	// As %.3g: the configured rates on the details page.
	for _, c := range []struct {
		lang string
		x    float64
		want string
	}{{"en", 2.5, "2.5"}, {"pt-BR", 2.5, "2,5"}, {"en", 95.5, "95.5"}, {"en", 0.375, "0.375"}, {"en", 12, "12"}, {"en", 0, "0"}, {"en", 33.333, "33.3"}} {
		if got := Significant(c.lang, c.x, 3); got != c.want {
			t.Errorf("Significant(%s, %v) = %q, want %q", c.lang, c.x, got, c.want)
		}
	}
}

func TestPluralCategoriesAsPython(t *testing.T) {
	for _, c := range []struct {
		lang string
		n    int64
		want string
	}{
		{"pt-BR", 0, "one"}, {"pt-BR", 1, "one"}, {"pt-BR", 2, "other"}, {"pt-PT", 0, "other"},
		{"zh-Hans", 1, "other"}, {"ru", 21, "one"}, {"ru", 11, "many"}, {"ar", 105, "few"}, {"ar", 100, "other"}, {"ar", 111, "many"},
		{"lv", 10, "zero"}, {"cy", 6, "many"}, {"sl", 102, "two"},
	} {
		if got := pluralCategory(c.lang, c.n); got != c.want {
			t.Errorf("plural(%s, %d) = %s, want %s", c.lang, c.n, got, c.want)
		}
	}
}

// expire makes the next For read the pack file again.
func expire() { checked = time.Time{} }

func writePack(t *testing.T, path string, pack map[string]any) {
	t.Helper()
	data, _ := json.Marshal(pack)
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestActivePack(t *testing.T) {
	dir := t.TempDir()
	active := filepath.Join(dir, "translation", "active.json")
	os.MkdirAll(filepath.Dir(active), 0o755)
	SetActive(active)
	defer SetActive("")

	if got := For("en").T("ingame.notices.tab.news", nil); got != "News" {
		t.Fatalf("no pack: %q", got)
	}
	writePack(t, active, map[string]any{"format": 1, "language": "pt-BR",
		"bunker": map[string]any{"ingame.notices.tab.news": "Notícias", "bad": 3},
		"game":   map[string]any{"mission.name.1": "Missão 1"},
		"master": map[string]any{"m_gift_text.25": "Presente"}})
	expire()
	en := For("en")
	if got := en.T("ingame.notices.tab.news", nil); got != "Notícias" {
		t.Errorf("pack: %q", got)
	}
	if en.Language() != "pt-BR" || en.Game("mission.name.1") != "Missão 1" || en.Master("m_gift_text.25") != "Presente" {
		t.Errorf("pack sections: %s %q %q", en.Language(), en.Game("mission.name.1"), en.Master("m_gift_text.25"))
	}
	// A Japanese or Korean client: the pack replaces the English slot only.
	if ja := For("ja"); ja.T("ingame.notices.tab.news", nil) != "News" || ja.Game("mission.name.1") != "" || ja.Language() != "en" {
		t.Errorf("ja client got the pack")
	}
	// A broken pack: English.
	os.WriteFile(active, []byte("{not json"), 0o644)
	expire()
	if got := For("en").T("ingame.notices.tab.news", nil); got != "News" {
		t.Errorf("broken pack: %q", got)
	}
	os.Remove(active)
	expire()
	if got := For("en").T("ingame.notices.tab.news", nil); got != "News" {
		t.Errorf("pack removed: %q", got)
	}
}

func TestPackReadAtMostOnceASecond(t *testing.T) {
	dir := t.TempDir()
	active := filepath.Join(dir, "active.json")
	SetActive(active)
	defer SetActive("")
	writePack(t, active, map[string]any{"format": 1, "language": "de", "bunker": map[string]any{"ingame.notices.tab.news": "Neues"}})
	expire()
	For("en")
	writePack(t, active, map[string]any{"format": 1, "language": "de", "bunker": map[string]any{"ingame.notices.tab.news": "Nachrichten!"}})
	if got := For("en").T("ingame.notices.tab.news", nil); got != "Neues" {
		t.Errorf("read again within a second: %q", got)
	}
	checked = checked.Add(-2 * time.Second)
	if got := For("en").T("ingame.notices.tab.news", nil); got != "Nachrichten!" {
		t.Errorf("not read after a second: %q", got)
	}
}
