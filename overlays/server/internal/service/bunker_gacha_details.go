package service

import (
	"database/sql"
	"fmt"
	"html"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"lunar-tear/server/internal/bunkercache"
	"lunar-tear/server/internal/gacha"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"

	_ "modernc.org/sqlite"
)

// archivePaths are where Bunker's Archive keeps its database, which holds the
// game's English text (banner, costume and weapon names): Android
// files/archive next to files/saves, iOS Library/Application Support/LunarArchive
// beside Documents/saves. Without it, the details page shows ids instead of names.
var archivePaths []string

// SetArchiveRoot finds the Archive database from the save folder.
func SetArchiveRoot(dataRoot string) {
	archivePaths = []string{
		filepath.Join(dataRoot, "..", "archive", "archive.db"),
		filepath.Join(dataRoot, "..", "..", "Library", "Application Support", "LunarArchive", "archive.db"),
	}
}

// gameText looks up English text by key, and costume assets (ch008001) by costume id.
type gameText struct {
	db   *sql.DB
	lang string // ja, ko: names from text_local first; en or "": English only

	missions []missionName // mission names in English and lang, read once for missionText
}

func openGameText() *gameText { return openGameTextIn("en") }

// openGameTextIn opens the Archive's text for pages in lang (ja, ko or en).
func openGameTextIn(lang string) *gameText {
	for _, p := range archivePaths {
		if _, err := os.Stat(p); err != nil {
			continue
		}
		db, err := sql.Open("sqlite", "file:"+p+"?mode=ro")
		if err == nil {
			return &gameText{db: db, lang: lang}
		}
	}
	return &gameText{lang: lang}
}

func (t *gameText) close() {
	if t.db != nil {
		t.db.Close()
	}
}

func (t *gameText) text(key string) string {
	if t.db == nil {
		return ""
	}
	if v := t.local(key); v != "" {
		return v
	}
	var v string
	t.db.QueryRow(`SELECT value FROM text WHERE key = ?`, key).Scan(&v)
	return v
}

func (t *gameText) costumeName(id int32) string {
	if t.db != nil {
		var asset string
		if t.db.QueryRow(`SELECT asset FROM costume WHERE costume = ?`, id).Scan(&asset) == nil {
			if name := t.text("costume.name." + asset); name != "" {
				return name
			}
		}
	}
	return fmt.Sprintf("Costume %d", id)
}

// weaponAssets maps a weapon id to its asset (wp001060), for its name.
var weaponAssets = bunkercache.Value(func() map[int32]string {
	assets := map[int32]string{}
	if rows, err := utils.ReadTable[masterdata.EntityMWeapon]("m_weapon"); err == nil {
		for _, w := range rows {
			assets[w.WeaponId] = fmt.Sprintf("wp%03d%03d", w.WeaponType, w.AssetVariationId)
		}
	}
	return assets
})

func (t *gameText) weaponName(id int32) string {
	if a, ok := weaponAssets()[id]; ok {
		if name := t.text("weapon.name." + a + ".1"); name != "" {
			return name
		}
	}
	return fmt.Sprintf("Weapon %d", id)
}

func (t *gameText) itemName(it masterdata.GachaPoolItem) string {
	if it.PossessionType == int32(model.PossessionTypeCostume) {
		return t.costumeName(it.PossessionId)
	}
	return t.weaponName(it.PossessionId)
}

func stars(rarity int32) string {
	switch rarity {
	case model.RaritySSRare:
		return "★4"
	case model.RaritySRare:
		return "★3"
	case model.RarityRare:
		return "★2"
	}
	return "★1"
}

func day(millis int64) string {
	return time.UnixMilli(gametime.ToView(millis)).UTC().Format("2006/01/02") // the original-dates view
}

// openEnded is where a summon's end stands for "never": the always-open ends
// (31 December 2099) and the placeholders a little before it.
const openEnded = int64(4070908800000) // 2099/01/01

// periodHTML is the summon's period line. A summon that never ends says so
// rather than showing a 2099 date; a ticket summon is open while you have one.
func periodHTML(e store.GachaCatalogEntry, ticket bool) string {
	if e.EndDatetime < openEnded {
		return fmt.Sprintf("<p class=k>%s – %s (UTC)</p>", day(e.StartDatetime), day(e.EndDatetime))
	}
	note := ""
	if ticket {
		note = ": open while you have a ticket"
	}
	return fmt.Sprintf("<p class=k>From %s (UTC) · no end date%s</p>", day(e.StartDatetime), note)
}

// eventPeriodHTML is an event summon's dates: its event's run open now,
// else the next, else the last. The calendar can move a run's row so that it
// ends before it starts; such a row is no run.
func eventPeriodHTML(runs [][2]int64, now int64) string {
	var open, next, last *[2]int64
	for i := range runs {
		r := &runs[i]
		switch {
		case r[1] < r[0]:
			continue
		case r[0] <= now && now < r[1]:
			open = r
		case r[0] > now && (next == nil || r[0] < next[0]):
			next = r
		case r[1] <= now && (last == nil || r[1] > last[1]):
			last = r
		}
	}
	for _, r := range []*[2]int64{open, next, last} {
		if r != nil {
			return fmt.Sprintf("<p class=k>%s – %s (UTC), with its event</p>", day(r[0]), day(r[1]))
		}
	}
	return "<p class=k>Opens when its event runs.</p>"
}

func (t *gameText) price(p store.GachaPricePhaseEntry) string {
	if p.Price == 0 {
		return "Free"
	}
	switch p.PriceType {
	case model.PriceTypeGem:
		return fmt.Sprintf("%d gems", p.Price)
	case model.PriceTypePaidGem:
		return fmt.Sprintf("%d paid gems", p.Price)
	case model.PriceTypeConsumableItem:
		name := "Summon Ticket"
		if n := possessionName(t, int32(model.PossessionTypeConsumableItem), p.PriceId); n != "" && !strings.HasPrefix(n, "Item ") {
			name = n // each event's own tickets
		} else if p.PriceId == model.ConsumableIdPremiumTicket {
			if n := t.text("consumable_item.name.200002"); n != "" {
				name = n
			}
		}
		return fmt.Sprintf("%d × %s", p.Price, name)
	}
	return fmt.Sprintf("%d", p.Price)
}

// itemRate is one item's share of every draw, in percent.
type itemRate struct {
	item     masterdata.GachaPoolItem
	percent  float64
	featured bool
}

// bannerRates works out each item's rate the way gacha.DrawPremium picks: a
// tier (type and rarity) by the summon rates; within a tier with featured
// items, a featured item FeaturedPercent of the time (each featured entry
// alike); otherwise any item of the tier's pool alike.
func bannerRates(bp *masterdata.BannerPool) []itemRate {
	return tierRates(bp, gacha.Rates().Tiers())
}

// slotRates are the rates of a guaranteed slot, the way gacha.DrawPremium and
// applyGuarantee fill it: a normal roll of minRarity or better stands, a lower
// one is rolled again among the tiers of minRarity or better; then, when the
// guarantee names what the slot may give (candidates), anything else is
// replaced by one of those, each alike.
func slotRates(bp *masterdata.BannerPool, minRarity int32, candidates []masterdata.GachaPoolItem) []itemRate {
	type key struct{ t, id int32 }
	var high []gacha.RateTier
	for _, t := range gacha.Rates().Tiers() {
		if t.RarityType >= minRarity {
			high = append(high, t)
		}
	}
	rates := tierRates(bp, high) // rescaled below to 100% in all
	total := 0.0
	for _, r := range rates {
		total += r.percent
	}
	if total == 0 {
		return nil
	}
	for i := range rates {
		rates[i].percent *= 100 / total
	}
	if len(candidates) == 0 {
		return rates
	}
	in := map[key]bool{}
	for _, c := range candidates {
		in[key{c.PossessionType, c.PossessionId}] = true
	}
	out := rates[:0]
	moved := 0.0
	for _, r := range rates {
		if in[key{r.item.PossessionType, r.item.PossessionId}] {
			out = append(out, r)
		} else {
			moved += r.percent
		}
	}
	have := map[key]int{}
	for i, r := range out {
		have[key{r.item.PossessionType, r.item.PossessionId}] = i
	}
	for _, c := range candidates {
		k := key{c.PossessionType, c.PossessionId}
		i, ok := have[k]
		if !ok {
			out = append(out, itemRate{item: c})
			i = len(out) - 1
			have[k] = i
		}
		out[i].percent += moved / float64(len(candidates))
	}
	sortRates(out)
	return out
}

// slotMin is the rarity a phase's guaranteed slot gives at least, as
// gacha's drawPremium raises it.
func slotMin(p store.GachaPricePhaseEntry) int32 {
	if g := gacha.Rates().GuaranteedRarity(); p.FixedRarityMin < g {
		return g
	}
	return p.FixedRarityMin
}

// guaranteedSlot gives the slot rates when every draw of every phase is a
// guaranteed slot of the same kind (ticket summons): then those are the
// summon's rates.
func guaranteedSlot(e *store.GachaCatalogEntry, bp *masterdata.BannerPool, pool *masterdata.GachaCatalog) ([]itemRate, bool) {
	if len(e.PricePhases) == 0 {
		return nil, false
	}
	first := e.PricePhases[0]
	for _, p := range e.PricePhases {
		if p.FixedCount <= 0 || p.FixedCount < p.DrawCount || p.FixedRarityMin != first.FixedRarityMin {
			return nil, false
		}
	}
	var candidates []masterdata.GachaPoolItem
	if rule, ok := masterdata.PhaseRuleFor(first.PhaseId); ok && pool != nil {
		candidates = gacha.GuaranteeCandidates(bp, pool, rule)
	}
	rates := slotRates(bp, slotMin(first), candidates)
	return rates, len(rates) > 0
}

func tierRates(bp *masterdata.BannerPool, tiers []gacha.RateTier) []itemRate {
	cfg := gacha.Rates()
	type key struct{ t, id int32 }
	rates := map[key]*itemRate{}
	addRate := func(it masterdata.GachaPoolItem, p float64, featured bool) {
		k := key{it.PossessionType, it.PossessionId}
		r := rates[k]
		if r == nil {
			r = &itemRate{item: it}
			rates[k] = r
		}
		r.percent += p
		r.featured = r.featured || featured
	}
	for _, tier := range tiers {
		percent := float64(tier.Weight) / 1000
		var featured []masterdata.GachaPoolItem
		for _, f := range bp.Featured {
			if f.PossessionType == tier.PossessionType && f.RarityType == tier.RarityType {
				featured = append(featured, f)
			}
		}
		pool := bp.WeaponsByRarity[tier.RarityType]
		if tier.PossessionType == int32(model.PossessionTypeCostume) {
			pool = bp.CostumesByRarity[tier.RarityType]
		}
		rest := percent
		if len(featured) > 0 {
			share := percent * cfg.FeaturedPercent / 100
			for _, f := range featured {
				addRate(f, share/float64(len(featured)), true)
			}
			rest -= share
		}
		for _, it := range pool {
			addRate(it, rest/float64(len(pool)), false)
		}
	}
	out := make([]itemRate, 0, len(rates))
	for _, r := range rates {
		out = append(out, *r)
	}
	sortRates(out)
	return out
}

func sortRates(out []itemRate) {
	sort.Slice(out, func(i, j int) bool {
		a, b := out[i], out[j]
		if a.item.RarityType != b.item.RarityType {
			return a.item.RarityType > b.item.RarityType
		}
		if a.featured != b.featured {
			return a.featured
		}
		if a.item.PossessionType != b.item.PossessionType {
			return a.item.PossessionType < b.item.PossessionType
		}
		return a.item.PossessionId < b.item.PossessionId
	})
}

// serveGachaDetailsPage answers the banner's "Details" button
// (/web/{lang}/gacha-details?gachaId=N): the banner's period, costs, medal
// exchange and every item it can give, with rates from Pod Programs > Summon rates.
func serveGachaDetailsPage(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.URL.Query().Get("gachaId"))
	var entry *store.GachaCatalogEntry
	var bp *masterdata.BannerPool
	var pool *masterdata.GachaCatalog
	if bunkerHolder != nil {
		c := bunkerHolder.Get()
		entry, _ = resolveGachaId(c.GachaEntries, int32(id))
		if c.GachaPool != nil && entry != nil {
			bp = c.GachaPool.BannerPools[entry.GachaId]
			pool = c.GachaPool
		}
	}
	t := openGameText()
	defer t.close()
	esc := html.EscapeString

	var b strings.Builder
	b.WriteString(`<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font:15px sans-serif;background:#d8d4c2;color:#3a372e;max-width:1000px;margin:16px auto;padding:0 16px}h1{font-size:18px;letter-spacing:.05em;margin:0 0 4px}
h2{font-size:15px;letter-spacing:.1em;border-bottom:2px solid #8f8b7a;padding-bottom:4px;margin:20px 0 6px}
table{border-collapse:collapse;width:100%}td{border-bottom:1px solid #a29f8f;padding:6px 4px;vertical-align:top}
td.n{text-align:right;white-space:nowrap}.f{font-weight:bold}.k{color:#6b6758;font-size:13px}p{line-height:1.5;margin:6px 0}
a.notice-link{display:inline-block;margin-top:4px;padding:4px 14px;background:#4b4341;color:#e6e2cf;text-decoration:none;font-size:14px}</style></head><body>`)
	if entry == nil {
		b.WriteString("<h1>SUMMONS DETAILS</h1><p>This summon is not on the local server.</p></body></html>")
		writeHTML(w, b.String())
		return
	}
	title := masterdata.SummonTitle(entry.BannerAssetName)
	if title == "" {
		title = t.text("gacha.title." + entry.BannerAssetName)
	}
	if title == "" {
		title = noticeSummonTitle(*entry)
	}
	if title == "" {
		title = fmt.Sprintf("Summons %d", entry.GachaId)
	}
	ticket := false
	for _, p := range entry.PricePhases {
		ticket = ticket || (p.PriceType == model.PriceTypeConsumableItem && p.Price > 0)
	}
	period := periodHTML(*entry, ticket)
	if _, _, ok := masterdata.EventSummonFor(entry.GachaId); ok {
		period = eventPeriodHTML(masterdata.EventSummonRuns(entry.GachaId), gametime.NowMillis())
	}
	fmt.Fprintf(&b, "<h1>%s</h1>%s", esc(title), period)
	b.WriteString(summonNoticeHTML(*entry))

	if len(entry.PricePhases) > 0 {
		b.WriteString("<h2>COST</h2><table>")
		for _, p := range entry.PricePhases {
			label := fmt.Sprintf("%d summon", p.DrawCount)
			if p.DrawCount != 1 {
				label += "s"
			}
			if p.StepNumber > 0 {
				label = fmt.Sprintf("Step %d: %s", p.StepNumber, label)
			}
			note := ""
			if p.FixedCount > 0 && p.FixedRarityMin > 0 {
				note = fmt.Sprintf("<br><span class=k>%d guaranteed %s or higher</span>", p.FixedCount, stars(p.FixedRarityMin))
			}
			if p.LimitExecCount > 0 {
				note += fmt.Sprintf("<br><span class=k>Up to %d times</span>", p.LimitExecCount)
			}
			fmt.Fprintf(&b, "<tr><td>%s%s</td><td class=n>%s</td></tr>", esc(label), note, esc(t.price(p)))
		}
		b.WriteString("</table>")
	}

	// Box summons draw only from their boxes: no premium pool rates.
	if prizes, ok := masterdata.PrizeBoxFor(entry.GachaId); ok {
		b.WriteString(prizeSectionHTML(r, entry.GachaId, prizes))
		b.WriteString("</body></html>")
		writeHTML(w, b.String())
		return
	}
	if box, _, ok := masterdata.EventSummonFor(entry.GachaId); ok {
		b.WriteString(eventBoxHTML(r, t, box))
		b.WriteString("</body></html>")
		writeHTML(w, b.String())
		return
	}

	if entry.MedalConsumableItemId != 0 {
		medal := "medals"
		if rows, err := utils.ReadTable[masterdata.EntityMConsumableItem]("m_consumable_item"); err == nil {
			for _, c := range rows {
				if c.ConsumableItemId == entry.MedalConsumableItemId {
					if n := t.text(fmt.Sprintf("consumable_item.name.%d%03d", c.AssetCategoryId, c.AssetVariationId)); n != "" {
						medal = n
					}
				}
			}
		}
		b.WriteString("<h2>EXCHANGE</h2>")
		fmt.Fprintf(&b, "<p>Each summon gives 1 %s. Trade them for featured items in the Exchange.", esc(medal))
		if entry.CeilingCount > 0 {
			fmt.Fprintf(&b, " A featured item costs %d.", entry.CeilingCount)
		}
		b.WriteString("</p>")
	}
	if len(entry.BoxContents) > 0 {
		names := map[int32]string{}
		for _, m := range table[masterdata.EntityMMaterial]("m_material") {
			names[m.MaterialId] = t.text(fmt.Sprintf("material.name.%d%03d", m.AssetCategoryId, m.AssetVariationId))
		}
		total := int32(0)
		for _, c := range entry.BoxContents {
			total += c.Count
		}
		fmt.Fprintf(&b, "<h2>BOX</h2><p class=k>Each box holds %d items, drawn without putting them back. It refills on the 1st of every month, and can be reset once its targets are drawn.</p><table>", total)
		for _, c := range entry.BoxContents {
			name := names[c.PossessionId]
			if name == "" {
				name = fmt.Sprintf("Material %d", c.PossessionId)
			}
			class := ""
			if c.IsTarget {
				class = " class=f"
			}
			fmt.Fprintf(&b, "<tr><td%s>%s %s</td><td class=n>×%d</td></tr>", class, stars(c.RarityType), esc(name), c.Count)
		}
		b.WriteString("</table></body></html>")
		writeHTML(w, b.String())
		return
	}

	if bp == nil {
		b.WriteString("<p>This summon gives items from its own list, not the premium pool.</p></body></html>")
		writeHTML(w, b.String())
		return
	}
	rates := bannerRates(bp)
	slot, everySlot := guaranteedSlot(entry, bp, pool)
	if everySlot {
		rates = slot
	}
	var featured []string
	for _, r := range rates {
		if r.featured {
			featured = append(featured, fmt.Sprintf("<tr><td class=f>%s %s</td><td class=n>%.3f%%</td></tr>", stars(r.item.RarityType), esc(t.itemName(r.item)), r.percent))
		}
	}
	if len(featured) > 0 {
		b.WriteString("<h2>FEATURED</h2><table>")
		b.WriteString(strings.Join(featured, ""))
		b.WriteString("</table>")
	}
	cfg := gacha.Rates()
	if everySlot {
		fmt.Fprintf(&b, "<h2>ALL ITEMS</h2><p class=k>Every summon here is guaranteed %s or higher; rates per summon. Set in Bunker: Pod Programs › Summon rates.</p><table>", stars(slotMin(entry.PricePhases[0])))
	} else {
		fmt.Fprintf(&b, "<h2>ALL ITEMS</h2><p class=k>Rates per summon. ★4 %.3g%%, ★3 %.3g%%, ★2 %.3g%%; a featured item %.3g%% of the time when one matches. Multi-step boosts and 10-summon guarantees are on top. Set in Bunker: Pod Programs › Summon rates.</p><table>",
			cfg.FourStarPercent, cfg.ThreeStarPercent, 100-cfg.FourStarPercent-cfg.ThreeStarPercent, cfg.FeaturedPercent)
	}
	for _, r := range rates {
		kind := "Weapon"
		if r.item.PossessionType == int32(model.PossessionTypeCostume) {
			kind = "Costume"
		}
		class := ""
		if r.featured {
			class = " class=f"
		}
		fmt.Fprintf(&b, "<tr><td%s>%s %s <span class=k>%s</span></td><td class=n>%.3f%%</td></tr>", class, stars(r.item.RarityType), esc(t.itemName(r.item)), kind, r.percent)
	}
	b.WriteString("</table></body></html>")
	writeHTML(w, b.String())
}

func writeHTML(w http.ResponseWriter, page string) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(page))
}

// serveGachaBoxPage is a box summon's "i" button (/web/<lang>/gacha/box): the
// summon's notice when it has one, else its details. The Rates button opens
// the same page with tab=Rate, and keeps the details with the prizes.
func serveGachaBoxPage(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	if q.Get("tab") != "Rate" && bunkerHolder != nil {
		id, _ := strconv.Atoi(q.Get("gachaId"))
		if entry, _ := resolveGachaId(bunkerHolder.Get().GachaEntries, int32(id)); entry != nil {
			activeNoticesMu.RLock()
			n := activeNotices
			activeNoticesMu.RUnlock()
			if notice := summonNotice(*entry); notice != 0 && n != nil && n.Title(notice) != "" {
				http.Redirect(w, r, fmt.Sprintf("/%s/information/?informationId=%d&isIngame=1", webLanguage(r.URL.Path), notice), http.StatusFound)
				return
			}
		}
	}
	serveGachaDetailsPage(w, r)
}

// noticeSummonTitle names a summon the game text has no title for by its
// notice ("Mama's Dream Summons On Now": "Mama's Dream Summons"); "" if none.
func noticeSummonTitle(entry store.GachaCatalogEntry) string {
	id := summonNotice(entry)
	activeNoticesMu.RLock()
	n := activeNotices
	activeNoticesMu.RUnlock()
	if id == 0 || n == nil {
		return ""
	}
	return trimNoticeTitle(n.Title(id))
}

// trimNoticeTitle is a notice title as a summon's ("… Summons On Now" and
// "… Summons Updated" read "… Summons").
func trimNoticeTitle(title string) string {
	return strings.TrimSuffix(strings.TrimSuffix(title, " On Now"), " Updated")
}

// webLanguage is the language of a /web/<lang>/... path, else English.
func webLanguage(path string) string {
	if parts := strings.Split(strings.TrimPrefix(path, "/"), "/"); len(parts) > 2 && parts[0] == "web" && noticePath.MatchString("/"+parts[1]+"/information/") {
		return parts[1]
	}
	return "en"
}
