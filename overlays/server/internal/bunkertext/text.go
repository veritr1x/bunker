// Package bunkertext is the text Bunker's server puts into the game (the summon details, the notices'
// tabs and labels, the panel pages), in the language of the active pack, with the same rules as
// Pod Programs and both launchers (bunker_text.py, BunkerText.java, LTText.m; the cases in
// android/tools/bunker_text_cases.json): English when a translation is missing, empty or broken
// (a placeholder it lacks or adds, a stray brace), CLDR plural forms, numbers the language's way.
//
// The English catalogue is translations/bunker/en.json (scripts/prepare.py copies it beside this file).
// A pack's "bunker" section translates it; its "game" and "master" sections name the game's own things.
// A pack replaces the game's English, so a Japanese or Korean client gets the English catalogue.
package bunkertext

import (
	_ "embed"
	"encoding/json"
	"sort"
	"strings"
)

//go:embed en.json
var englishJSON []byte

var english = func() map[string]string {
	out := map[string]string{}
	json.Unmarshal(englishJSON, &out)
	return out
}()

// Texts is the catalogue in one language, with its pack's game and master texts.
type Texts struct {
	english, translation, game, master map[string]string
	language                           string
}

func newTexts(english map[string]string, language string, translation map[string]string) *Texts {
	t := &Texts{english: english, translation: clean(translation), language: "en"}
	if len(t.translation) > 0 && language != "" {
		t.language = language
	}
	return t
}

func clean(texts map[string]string) map[string]string {
	out := map[string]string{}
	for k, v := range texts {
		if v != "" {
			out[k] = v
		}
	}
	return out
}

// Language is the language the texts are in (a BCP 47 tag), "en" without a pack.
func (t *Texts) Language() string { t = t.or(); return t.language }

// Game is the pack's text for one of the game's keys ("mission.name.1"), "" without one.
func (t *Texts) Game(key string) string { t = t.or(); return t.game[key] }

// Master is the pack's text for a master data row ("m_webview_mission_title_text.3"), "" without one.
func (t *Texts) Master(key string) string { t = t.or(); return t.master[key] }

// Number is n written the texts' language's way.
func (t *Texts) Number(n int64) string { t = t.or(); return Number(t.language, n) }

// Decimal is x with places decimals, the texts' language's way.
func (t *Texts) Decimal(x float64, places int) string {
	t = t.or()
	return Decimal(t.language, x, places)
}

// Significant is x to digits significant digits, the texts' language's way.
func (t *Texts) Significant(x float64, digits int) string {
	t = t.or()
	return Significant(t.language, x, digits)
}

// or is t, or the English catalogue for a nil Texts.
func (t *Texts) or() *Texts {
	if t == nil {
		return plain
	}
	return t
}

type field struct{ name, spec, conversion string }

// fields are the placeholders in text, or ok=false when it is not a valid template (an unclosed or
// stray brace). Doubled braces are braces.
func fields(text string) (out []field, ok bool) {
	for i := 0; i < len(text); i++ {
		switch text[i] {
		case '{':
			if i+1 < len(text) && text[i+1] == '{' {
				i++
				continue
			}
			end := strings.IndexByte(text[i+1:], '}')
			if end < 0 {
				return nil, false
			}
			inner := text[i+1 : i+1+end]
			if strings.ContainsRune(inner, '{') {
				return nil, false
			}
			var f field
			f.name, f.spec, _ = strings.Cut(inner, ":")
			f.name, f.conversion, _ = strings.Cut(f.name, "!")
			out = append(out, f)
			i += end + 1
		case '}':
			if i+1 < len(text) && text[i+1] == '}' {
				i++
				continue
			}
			return nil, false
		}
	}
	sort.Slice(out, func(a, b int) bool {
		x, y := out[a], out[b]
		if x.name != y.name {
			return x.name < y.name
		}
		if x.spec != y.spec {
			return x.spec < y.spec
		}
		return x.conversion < y.conversion
	})
	return out, true
}

func sameFields(a, b []field) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func subset(a, b []field) bool {
	in := map[field]bool{}
	for _, f := range b {
		in[f] = true
	}
	for _, f := range a {
		if !in[f] {
			return false
		}
	}
	return true
}

// format puts params in text's placeholders; ok=false when one has no value, a spec or a conversion,
// or no name.
func format(text string, params map[string]string) (string, bool) {
	var b strings.Builder
	for i := 0; i < len(text); i++ {
		c := text[i]
		switch {
		case c == '{' && i+1 < len(text) && text[i+1] == '{', c == '}' && i+1 < len(text) && text[i+1] == '}':
			b.WriteByte(c)
			i++
		case c == '{':
			end := strings.IndexByte(text[i+1:], '}')
			if end < 0 {
				return "", false
			}
			name := text[i+1 : i+1+end]
			value, has := params[name]
			if !has || name == "" || strings.ContainsAny(name, ":!{") {
				return "", false
			}
			b.WriteString(value)
			i += end + 1
		case c == '}':
			return "", false
		default:
			b.WriteByte(c)
		}
	}
	return b.String(), true
}

func formatOrAsIs(text string, params map[string]string) string {
	if out, ok := format(text, params); ok {
		return out
	}
	return text
}

// T is key's text in the language, else English; the key itself when the catalogue lacks it.
func (t *Texts) T(key string, params map[string]string) string {
	t = t.or()
	if _, ok := t.english[key]; !ok {
		return key
	}
	return t.TOr(key, key, params)
}

// TOr is T, with fallback when the catalogue lacks key.
func (t *Texts) TOr(key, fallback string, params map[string]string) string {
	t = t.or()
	base, ok := t.english[key]
	if !ok {
		return fallback
	}
	if translated, has := t.translation[key]; has {
		mine, okMine := fields(translated)
		theirs, okBase := fields(base)
		if okMine && okBase && sameFields(mine, theirs) {
			if out, ok := format(translated, params); ok {
				return out
			}
		}
	}
	return formatOrAsIs(base, params)
}

// forms are the translation's plural forms of key when they cover every form the language uses and
// each takes only placeholders the English has; nil otherwise.
func (t *Texts) forms(key string) map[string]string {
	other, ok := t.english[key+".other"]
	if !ok || len(t.translation) == 0 {
		return nil
	}
	allowed, okAllowed := fields(other)
	if !okAllowed {
		return nil
	}
	needed := pluralCategories(t.language)
	out := map[string]string{}
	for _, category := range allCategories {
		text, has := t.translation[key+"."+category]
		if !has {
			if needed[category] {
				return nil
			}
			continue
		}
		f, valid := fields(text)
		if !valid || !subset(f, allowed) {
			if needed[category] {
				return nil
			}
			continue
		}
		out[category] = text
	}
	return out
}

// Count is key in the plural form the language uses for n (".one", ".few", ".other"…); {n} is the
// count, written the language's way. A translation missing a form its language needs gives the English.
func (t *Texts) Count(key string, n int64, params map[string]string) string {
	t = t.or()
	values := map[string]string{"n": t.Number(n)}
	for k, v := range params {
		values[k] = v
	}
	if forms := t.forms(key); forms != nil {
		if out, ok := format(forms[pluralCategory(t.language, n)], values); ok {
			return out
		}
	}
	form := key + ".other"
	if n == 1 {
		form = key + ".one"
	}
	base, ok := t.english[form]
	if !ok {
		return key + ".other"
	}
	return formatOrAsIs(base, values)
}
