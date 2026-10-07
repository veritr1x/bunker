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
	"sync"
	"time"

	"lunar-tear/server/internal/gacha"
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
	db *sql.DB
}

func openGameText() *gameText {
	for _, p := range archivePaths {
		if _, err := os.Stat(p); err != nil {
			continue
		}
		db, err := sql.Open("sqlite", "file:"+p+"?mode=ro")
		if err == nil {
			return &gameText{db: db}
		}
	}
	return &gameText{}
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

var (
	weaponAssetsOnce sync.Once
	weaponAssets     map[int32]string // weapon id -> asset (wp001060), for its name
)

func (t *gameText) weaponName(id int32) string {
	weaponAssetsOnce.Do(func() {
		weaponAssets = map[int32]string{}
		if rows, err := utils.ReadTable[masterdata.EntityMWeapon]("m_weapon"); err == nil {
			for _, w := range rows {
				weaponAssets[w.WeaponId] = fmt.Sprintf("wp%03d%03d", w.WeaponType, w.AssetVariationId)
			}
		}
	})
	if a, ok := weaponAssets[id]; ok {
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
	return time.UnixMilli(millis).UTC().Format("2006/01/02")
}

func (t *gameText) price(p store.GachaPricePhaseEntry) string {
	switch p.PriceType {
	case model.PriceTypeGem:
		return fmt.Sprintf("%d gems", p.Price)
	case model.PriceTypePaidGem:
		return fmt.Sprintf("%d paid gems", p.Price)
	case model.PriceTypeConsumableItem:
		name := "Summon Ticket"
		if p.PriceId == model.ConsumableIdPremiumTicket {
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
	for _, tier := range cfg.Tiers() {
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
	return out
}

// serveGachaDetailsPage answers the banner's "Details" button
// (/web/{lang}/gacha-details?gachaId=N): the banner's period, costs, medal
// exchange and every item it can give, with rates from Pod Programs > Summon rates.
func serveGachaDetailsPage(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.URL.Query().Get("gachaId"))
	var entry *store.GachaCatalogEntry
	var bp *masterdata.BannerPool
	if bunkerHolder != nil {
		c := bunkerHolder.Get()
		for i := range c.GachaEntries {
			if c.GachaEntries[i].GachaId == int32(id) {
				entry = &c.GachaEntries[i]
				break
			}
		}
		if c.GachaPool != nil {
			bp = c.GachaPool.BannerPools[int32(id)]
		}
	}
	t := openGameText()
	defer t.close()
	esc := html.EscapeString

	var b strings.Builder
	b.WriteString(`<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font:15px sans-serif;background:#d8d4c2;color:#3a372e;margin:16px}h1{font-size:18px;letter-spacing:.05em;margin:0 0 4px}
h2{font-size:15px;letter-spacing:.1em;border-bottom:2px solid #8f8b7a;padding-bottom:4px;margin:20px 0 6px}
table{border-collapse:collapse;width:100%}td{border-bottom:1px solid #a29f8f;padding:6px 4px;vertical-align:top}
td.n{text-align:right;white-space:nowrap}.f{font-weight:bold}.k{color:#6b6758;font-size:13px}p{line-height:1.5;margin:6px 0}</style></head><body>`)
	if entry == nil {
		b.WriteString("<h1>SUMMONS DETAILS</h1><p>This summon is not on the local server.</p></body></html>")
		writeHTML(w, b.String())
		return
	}
	title := t.text("gacha.title." + entry.BannerAssetName)
	if title == "" {
		title = fmt.Sprintf("Summons %d", entry.GachaId)
	}
	fmt.Fprintf(&b, "<h1>%s</h1><p class=k>%s – %s (UTC)</p>", esc(title), day(entry.StartDatetime), day(entry.EndDatetime))

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

	if bp == nil {
		b.WriteString("<p>This summon gives items from its own list, not the premium pool.</p></body></html>")
		writeHTML(w, b.String())
		return
	}
	rates := bannerRates(bp)
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
	fmt.Fprintf(&b, "<h2>ALL ITEMS</h2><p class=k>Rates per summon. ★4 %.3g%%, ★3 %.3g%%, ★2 %.3g%%; a featured item %.3g%% of the time when one matches. Multi-step boosts and 10-summon guarantees are on top. Set in Bunker: Pod Programs › Summon rates.</p><table>",
		cfg.FourStarPercent, cfg.ThreeStarPercent, 100-cfg.FourStarPercent-cfg.ThreeStarPercent, cfg.FeaturedPercent)
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
