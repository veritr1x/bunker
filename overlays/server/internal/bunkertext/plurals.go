package bunkertext

import "strings"

// Which plural form a language uses for a whole number (CLDR 44), as bunker_plurals.py: the same languages,
// the same rules. Any other language uses English's: "one" for 1, "other" for everything else.

type pluralRule func(n int64) string

func onlyOther(int64) string { return "other" }

func oneFor1(n int64) string {
	if n == 1 {
		return "one"
	}
	return "other"
}

func oneFor01(n int64) string {
	if n == 0 || n == 1 {
		return "one"
	}
	return "other"
}

func slavic(rest string) pluralRule {
	return func(n int64) string {
		switch {
		case n%10 == 1 && n%100 != 11:
			return "one"
		case n%10 >= 2 && n%10 <= 4 && !(n%100 >= 12 && n%100 <= 14):
			return "few"
		}
		return rest
	}
}

func polish(n int64) string {
	switch {
	case n == 1:
		return "one"
	case n%10 >= 2 && n%10 <= 4 && !(n%100 >= 12 && n%100 <= 14):
		return "few"
	}
	return "many"
}

func czech(n int64) string {
	switch {
	case n == 1:
		return "one"
	case n >= 2 && n <= 4:
		return "few"
	}
	return "other"
}

func lithuanian(n int64) string {
	teen := n%100 >= 11 && n%100 <= 19
	switch {
	case n%10 == 1 && !teen:
		return "one"
	case n%10 >= 2 && !teen:
		return "few"
	}
	return "other"
}

func latvian(n int64) string {
	switch {
	case n%10 == 0 || (n%100 >= 11 && n%100 <= 19):
		return "zero"
	case n%10 == 1 && n%100 != 11:
		return "one"
	}
	return "other"
}

func romanian(n int64) string {
	switch {
	case n == 1:
		return "one"
	case n == 0 || (n%100 >= 2 && n%100 <= 19):
		return "few"
	}
	return "other"
}

func slovenian(n int64) string {
	switch n % 100 {
	case 1:
		return "one"
	case 2:
		return "two"
	case 3, 4:
		return "few"
	}
	return "other"
}

func arabic(n int64) string {
	switch {
	case n <= 2:
		return [...]string{"zero", "one", "two"}[n]
	case n%100 >= 3 && n%100 <= 10:
		return "few"
	case n%100 >= 11:
		return "many"
	}
	return "other"
}

func hebrew(n int64) string {
	switch n {
	case 1:
		return "one"
	case 2:
		return "two"
	}
	return "other"
}

func irish(n int64) string {
	switch {
	case n == 1:
		return "one"
	case n == 2:
		return "two"
	case n >= 3 && n <= 6:
		return "few"
	case n >= 7 && n <= 10:
		return "many"
	}
	return "other"
}

func welsh(n int64) string {
	switch n {
	case 0:
		return "zero"
	case 1:
		return "one"
	case 2:
		return "two"
	case 3:
		return "few"
	case 6:
		return "many"
	}
	return "other"
}

func icelandic(n int64) string {
	if n%10 == 1 && n%100 != 11 {
		return "one"
	}
	return "other"
}

var pluralRules = map[string]pluralRule{}

func init() {
	set := func(rule pluralRule, langs ...string) {
		for _, l := range langs {
			pluralRules[l] = rule
		}
	}
	set(onlyOther, "ja", "ko", "zh", "yue", "vi", "th", "id", "ms", "km", "lo", "my", "jv", "su", "bo", "dz")
	set(oneFor01, "fr", "pt", "hy", "ff", "kab", "hi", "bn", "gu", "kn", "mr", "zu", "am", "fa", "as")
	set(slavic("many"), "ru", "uk", "be")
	set(slavic("other"), "hr", "sr", "bs")
	set(polish, "pl")
	set(czech, "cs", "sk")
	set(lithuanian, "lt")
	set(latvian, "lv")
	set(romanian, "ro", "mo")
	set(slovenian, "sl")
	set(arabic, "ar")
	set(hebrew, "he", "iw")
	set(irish, "ga")
	set(welsh, "cy")
	set(icelandic, "is", "mk")
}

// pluralRegions are regions whose rule differs from their language's.
var pluralRegions = map[string]pluralRule{"pt-pt": oneFor1}

func ruleFor(language string) pluralRule {
	parts := tagParts(language)
	for depth := len(parts); depth > 0; depth-- {
		if r, ok := pluralRegions[strings.Join(parts[:depth], "-")]; ok {
			return r
		}
	}
	if r, ok := pluralRules[parts[0]]; ok {
		return r
	}
	return oneFor1
}

func tagParts(language string) []string {
	if language == "" {
		language = "en"
	}
	return strings.Split(strings.ToLower(strings.ReplaceAll(language, "_", "-")), "-")
}

func pluralCategory(language string, n int64) string {
	if n < 0 {
		n = -n
	}
	return ruleFor(language)(n)
}

// pluralCategories is every category language uses for whole numbers.
func pluralCategories(language string) map[string]bool {
	rule := ruleFor(language)
	out := map[string]bool{}
	for n := int64(0); n < 1200; n++ {
		out[rule(n)] = true
	}
	return out
}

var allCategories = []string{"zero", "one", "two", "few", "many", "other"}
