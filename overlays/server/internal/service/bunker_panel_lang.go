package service

import (
	"fmt"
	"regexp"
	"strings"

	"lunar-tear/server/internal/bunkertext"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/missions"
	"lunar-tear/server/internal/utils"
)

// Pages the game shows in its language (the Anecdotes' panel sheets) name
// things in it: the Archive indexes the game's Japanese and Korean text
// (text_local) beside its English, and the master data has each sheet's
// title and story in all three (LanguageType 1, 2 and 3).

// panelLanguage is the page's language as its requests give it
// (commonRequest.language: "Japanese", or a code like "ja-JP"): ja, ko or en.
func panelLanguage(language string) string {
	l := strings.ToLower(language)
	switch {
	case l == "japanese" || strings.HasPrefix(l, "ja"):
		return "ja"
	case l == "korean" || strings.HasPrefix(l, "ko"):
		return "ko"
	}
	return "en"
}

// languageType is the master data's LanguageType for lang.
func languageType(lang string) int32 {
	switch lang {
	case "ja":
		return 1
	case "ko":
		return 3
	}
	return 2
}

// local is key's text in the page's language, or "": on an English client the
// active pack's, else the Archive's other languages (none in an Archive built
// before it indexed them, or for a key it lacks).
func (t *gameText) local(key string) string {
	if t.lang == "" || t.lang == "en" {
		if t.words == nil {
			return ""
		}
		return t.words.Game(key)
	}
	if t.db == nil {
		return ""
	}
	var v string
	t.db.QueryRow(`SELECT value FROM text_local WHERE lang = ? AND key = ?`, t.lang, key).Scan(&v)
	return v
}

type missionName struct{ english, local string }

var digits = regexp.MustCompile(`\d+`)

// missionText is a panel's English title in the page's language: the game's
// mission of that wording, or of the same wording with other numbers (the
// panel's numbers go in their place). A title no mission has stays English.
func (t *gameText) missionText(english string) string {
	if t.db == nil {
		return english
	}
	if t.missions == nil {
		t.missions = []missionName{}
		fromPack := t.lang == "" || t.lang == "en" // an English client: the pack's names (none without a pack)
		query, args := `SELECT e.key, e.value, l.value FROM text e JOIN text_local l ON l.key = e.key AND l.lang = ?
			WHERE e.key LIKE 'mission.name.%' ORDER BY e.key`, []any{t.lang}
		if fromPack {
			query, args = `SELECT key, value, '' FROM text WHERE key LIKE 'mission.name.%' ORDER BY key`, nil
		}
		rows, err := t.db.Query(query, args...)
		if err == nil {
			for rows.Next() {
				var key string
				var m missionName
				if rows.Scan(&key, &m.english, &m.local) != nil {
					continue
				}
				if fromPack {
					m.local = t.local(key)
				}
				if m.local != "" {
					t.missions = append(t.missions, m)
				}
			}
			rows.Close()
		}
	}
	for _, m := range t.missions {
		if m.english == english {
			return m.local
		}
	}
	want := digits.ReplaceAllString(english, "#")
	numbers := digits.FindAllString(english, -1)
	for _, m := range t.missions {
		if digits.ReplaceAllString(m.english, "#") != want {
			continue
		}
		// Each of the mission's English numbers becomes the panel's; the
		// translation must carry the same numbers to be rewritten safely.
		theirs := digits.FindAllString(m.english, -1)
		swap := map[string]string{}
		for i, n := range theirs {
			if old, ok := swap[n]; ok && old != numbers[i] {
				swap = nil
				break
			}
			swap[n] = numbers[i]
		}
		if swap == nil || !sameNumbers(theirs, digits.FindAllString(m.local, -1)) {
			continue
		}
		return digits.ReplaceAllStringFunc(m.local, func(n string) string { return swap[n] })
	}
	return english
}

func sameNumbers(a, b []string) bool {
	count := map[string]int{}
	for _, n := range a {
		count[n]++
	}
	for _, n := range b {
		count[n]--
	}
	for _, c := range count {
		if c != 0 {
			return false
		}
	}
	return len(a) == len(b)
}

// panelTitle is the sheet's title in lang from the master data, or fallback
// (the English one the sheets carry); in English, the active pack's master text for it.
func panelTitle(run missions.PanelRun, lang, fallback string) string {
	var titleId int32
	rows, _ := utils.ReadTable[masterdata.EntityMWebviewMission]("m_webview_mission")
	for _, m := range rows {
		if m.WebviewMissionId == run.Id {
			titleId = m.TitleTextId
		}
	}
	if lang == "en" {
		if s := bunkertext.For("en").Master(fmt.Sprintf("m_webview_mission_title_text.%d", titleId)); titleId != 0 && s != "" {
			return s
		}
		return fallback
	}
	titles, _ := utils.ReadTable[masterdata.EntityMWebviewMissionTitleText]("m_webview_mission_title_text")
	for _, r := range titles {
		if titleId != 0 && r.WebviewMissionTitleTextId == titleId && r.LanguageType == languageType(lang) && r.Text != "" {
			return r.Text
		}
	}
	return fallback
}

// storyFor is story id's text in lang: in English, the active pack's master text for it first.
func storyFor(id int32, byLanguage map[int32]string, lang string) string {
	if lang == "en" || lang == "" {
		if s := bunkertext.For("en").Master(fmt.Sprintf("m_webview_panel_mission_complete_flavor_text.%d", id)); id != 0 && s != "" {
			return s
		}
	}
	return flavorIn(byLanguage, lang)
}

// flavorIn is a story in lang, else in English, else in the one language the
// master has (the Japanese master has only Japanese).
func flavorIn(byLanguage map[int32]string, lang string) string {
	for _, l := range []int32{languageType(lang), 2, 1, 3} {
		if s := byLanguage[l]; s != "" {
			return s
		}
	}
	return ""
}
