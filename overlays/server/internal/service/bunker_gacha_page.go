package service

import (
	"html"
	"net/http"
	"strings"

	"lunar-tear/server/internal/bunkertext"
	"lunar-tear/server/internal/gacha"
)

// serveGachaRatePage answers the game's "Rates" button with the rates in force
// (Pod Programs > Summon rates), so what it shows is what draws use. Its words
// follow the active pack, as the summon details do.
func serveGachaRatePage(w http.ResponseWriter) {
	words := bunkertext.For("en")
	c := gacha.Rates()
	pct := func(x float64) string {
		return words.T("ingame.rates.percent", map[string]string{"percent": words.Significant(x, 3)})
	}
	row := func(key, rarity string, percent float64) string {
		return "<tr><td>" + say(words, key, map[string]string{"rarity": rarity}) + "</td><td>" + escText.Replace(pct(percent)) + "</td></tr>"
	}
	fs, ts := c.FourCostumeShare/100, c.ThreeCostumeShare/100
	var b strings.Builder
	b.WriteString(`<!DOCTYPE html><html lang="` + html.EscapeString(words.Language()) + `"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font:15px sans-serif;background:#d8d4c2;color:#3a372e;max-width:1000px;margin:16px auto;padding:0 16px}h1{font-size:18px;letter-spacing:.1em;text-transform:uppercase}
table{border-collapse:collapse;width:100%;margin:8px 0 16px}td{border-bottom:1px solid #a29f8f;padding:6px 4px}td:last-child{text-align:right}
p{line-height:1.5}</style></head><body><h1>` + say(words, "ingame.rates.title", nil) + `</h1><table>`)
	b.WriteString(row("ingame.rates.costume", "★4", c.FourStarPercent*fs))
	b.WriteString(row("ingame.rates.weapon", "★4", c.FourStarPercent*(1-fs)))
	b.WriteString(row("ingame.rates.costume", "★3", c.ThreeStarPercent*ts))
	b.WriteString(row("ingame.rates.weapon", "★3", c.ThreeStarPercent*(1-ts)))
	b.WriteString(row("ingame.rates.weapon", "★2", 100-c.FourStarPercent-c.ThreeStarPercent))
	b.WriteString("</table>")
	b.WriteString("<p>" + say(words, "ingame.rates.featured", map[string]string{"percent": words.Significant(c.FeaturedPercent, 3)}) + "</p>")
	b.WriteString("<p>" + say(words, "ingame.rates.multi", map[string]string{"rarity": "★" + words.Number(int64(c.MultiMinRarity))}) + "</p>")
	if c.StepUpBoost {
		b.WriteString("<p>" + say(words, "ingame.rates.step_up", nil) + "</p>")
	}
	b.WriteString("<p>" + say(words, "ingame.rates.set_in", nil) + "</p></body></html>")
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(b.String()))
}
