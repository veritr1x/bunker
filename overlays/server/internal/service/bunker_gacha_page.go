package service

import (
	"fmt"
	"html"
	"net/http"
	"strings"

	"lunar-tear/server/internal/gacha"
)

// serveGachaRatePage answers the game's "Rates" button with the rates in force
// (Pod Programs > Summon rates), so what it shows is what draws use.
func serveGachaRatePage(w http.ResponseWriter) {
	c := gacha.Rates()
	row := func(label string, percent float64) string {
		return fmt.Sprintf("<tr><td>%s</td><td>%.3g%%</td></tr>", html.EscapeString(label), percent)
	}
	fs, ts := c.FourCostumeShare/100, c.ThreeCostumeShare/100
	var b strings.Builder
	b.WriteString(`<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font:15px sans-serif;background:#d8d4c2;color:#3a372e;margin:16px}h1{font-size:18px;letter-spacing:.1em}
table{border-collapse:collapse;width:100%;margin:8px 0 16px}td{border-bottom:1px solid #a29f8f;padding:6px 4px}td:last-child{text-align:right}
p{line-height:1.5}</style></head><body><h1>RATES</h1><table>`)
	b.WriteString(row("★4 costume", c.FourStarPercent*fs))
	b.WriteString(row("★4 weapon", c.FourStarPercent*(1-fs)))
	b.WriteString(row("★3 costume", c.ThreeStarPercent*ts))
	b.WriteString(row("★3 weapon", c.ThreeStarPercent*(1-ts)))
	b.WriteString(row("★2 weapon", 100-c.FourStarPercent-c.ThreeStarPercent))
	b.WriteString("</table>")
	fmt.Fprintf(&b, "<p>When a draw lands on a rarity and type that has featured items, it is a featured item %.3g%% of the time.</p>", c.FeaturedPercent)
	fmt.Fprintf(&b, "<p>The last draw of a 10-draw is ★%d or higher.</p>", c.MultiMinRarity)
	if c.StepUpBoost {
		b.WriteString("<p>Multi-step summons raise the ★4 rate 1.5× on steps 1 and 3 and 2× on step 5, and step 5 guarantees a ★4.</p>")
	}
	b.WriteString("<p>Set in Bunker: Pod Programs › Summon rates.</p></body></html>")
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(b.String()))
}
