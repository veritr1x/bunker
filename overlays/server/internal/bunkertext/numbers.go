package bunkertext

import (
	"math"
	"strconv"
	"strings"
)

// How each language writes a number (CLDR, Latin digits), as bunker_numbers.py.

type numberStyle struct {
	group, decimal string
	smallest       int  // fewest digits grouped (5: "1200" but "12 000")
	indian         bool // 12,34,567
}

const (
	nbsp  = " "
	nnbsp = " "
)

var (
	styleComma  = numberStyle{",", ".", 4, false}
	styleDot    = numberStyle{".", ",", 4, false}
	styleDot5   = numberStyle{".", ",", 5, false}
	styleSpace  = numberStyle{nbsp, ",", 4, false}
	styleSpace5 = numberStyle{nbsp, ",", 5, false}
	styleIndian = numberStyle{",", ".", 4, true}
	styleSwiss  = numberStyle{"'", ".", 4, false}
)

var numberStyles = map[string]numberStyle{"fr": {nnbsp, ",", 4, false}}

var numberRegions = map[string]numberStyle{
	"de-ch": styleSwiss, "de-li": styleSwiss, "en-ch": styleSwiss,
	"fr-ch": {"'", ",", 4, false}, "it-ch": {"'", ".", 5, false},
	"es-mx": styleComma, "es-419": styleComma, "es-us": styleComma,
	"de-at": styleSpace, "fr-ca": styleSpace, "en-za": styleSpace,
	"pt-pt": styleSpace5, "en-in": styleIndian,
}

func init() {
	set := func(s numberStyle, langs string) {
		for _, l := range strings.Fields(langs) {
			numberStyles[l] = s
		}
	}
	set(styleComma, "en ja zh ko ar he ms th fa ur kn si km my mn sw zu fil ga cy mt am")
	set(styleIndian, "hi bn mr ta te gu ml pa ne")
	set(styleDot, "de pt nl tr da id vi ro el hr sr bs mk ca eu gl lo az is ps lb")
	set(styleDot5, "es it sl")
	set(styleSpace, "ru cs sv nb no nn fi uk lt sk kk uz af ky tg")
	set(styleSpace5, "pl be hu bg et lv sq ka hy")
}

func styleFor(language string) numberStyle {
	parts := tagParts(language)
	for depth := len(parts); depth > 1; depth-- {
		if s, ok := numberRegions[strings.Join(parts[:depth], "-")]; ok {
			return s
		}
	}
	if s, ok := numberStyles[parts[0]]; ok {
		return s
	}
	return styleComma
}

func group(whole string, s numberStyle) string {
	if len(whole) < s.smallest {
		return whole
	}
	groups := []string{whole[len(whole)-3:]}
	rest, size := whole[:len(whole)-3], 3
	if s.indian {
		size = 2
	}
	for rest != "" {
		cut := max(0, len(rest)-size)
		groups = append([]string{rest[cut:]}, groups...)
		rest = rest[:cut]
	}
	return strings.Join(groups, s.group)
}

// Number is the whole number n as language writes it ("1,200", "1.200", "1 200").
func Number(language string, n int64) string {
	s := styleFor(language)
	whole := strconv.FormatUint(uint64(abs(n)), 10)
	if n < 0 {
		return "-" + group(whole, s)
	}
	return group(whole, s)
}

// Decimal is x with exactly places decimals, as language writes it ("2,500" in Portuguese).
func Decimal(language string, x float64, places int) string {
	if math.IsNaN(x) || math.IsInf(x, 0) {
		return strconv.FormatFloat(x, 'f', -1, 64)
	}
	s := styleFor(language)
	text := strconv.FormatFloat(math.Abs(x), 'f', places, 64)
	whole, fraction, _ := strings.Cut(text, ".")
	out := group(whole, s)
	if fraction != "" {
		out += s.decimal + fraction
	}
	if x < 0 && strings.Trim(text, "0.") != "" {
		out = "-" + out
	}
	return out
}

// Significant is x to digits significant digits, no trailing zeros, as language writes it
// ("2,5" in Portuguese for 2.5 at three digits).
func Significant(language string, x float64, digits int) string {
	if x == 0 || math.IsNaN(x) || math.IsInf(x, 0) {
		return Decimal(language, x, 0)
	}
	magnitude := int(math.Floor(math.Log10(math.Abs(x))))
	places := max(0, digits-1-magnitude)
	text := strings.TrimRight(strings.TrimRight(strconv.FormatFloat(x, 'f', places, 64), "0"), ".")
	if !strings.Contains(text, ".") {
		return Decimal(language, x, 0)
	}
	_, fraction, _ := strings.Cut(text, ".")
	return Decimal(language, x, len(fraction))
}

func abs(n int64) int64 {
	if n < 0 {
		return -n
	}
	return n
}
