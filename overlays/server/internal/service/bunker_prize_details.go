package service

import (
	"fmt"
	"html"
	"net/http"
	"strconv"
	"strings"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/bunkertext"
	"lunar-tear/server/internal/gacha"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// userLoader reads a player's save for the summon web pages (read only).
type userLoader interface {
	LoadUser(userId int64) (store.UserState, error)
}

var webUsers userLoader

// SetWebUsers lets the summon pages read the player's save; nil: they don't.
func SetWebUsers(u userLoader) { webUsers = u }

// prizeSectionHTML lists a prize box summon's prizes for Summons Details:
// each with its amount and, for limited ones, how many the player's box has
// left (the game passes the player as userId), else the notice's stock.
func prizeSectionHTML(r *http.Request, words *bunkertext.Texts, gachaId int32, prizes []masterdata.Prize) string {
	var left []int32
	if webUsers != nil {
		if id, err := strconv.ParseInt(r.URL.Query().Get("userId"), 10, 64); err == nil && id > 0 {
			if user, err := webUsers.LoadUser(id); err == nil {
				bs := user.Gacha.BannerStates[gachaId]
				left = gacha.PrizesLeft(&bs, prizes)
			}
		}
	}
	esc := html.EscapeString
	n := func(v int32) string { return words.Number(int64(v)) }
	var b strings.Builder
	b.WriteString("<h2>" + escText.Replace(words.T("ingame.summons.prizes", nil)) + "</h2><table>")
	for i, p := range prizes {
		have := words.T("ingame.summons.unlimited", nil)
		if p.Stock > 0 {
			have = words.T("ingame.summons.stock", map[string]string{"n": n(p.Stock)})
			if left != nil {
				have = words.T("ingame.summons.left", map[string]string{"left": n(left[i]), "n": n(p.Stock)})
			}
		}
		fmt.Fprintf(&b, "<tr><td>%s ×%s</td><td class=n>%s</td></tr>", esc(p.Name), esc(n(p.Qty)), escText.Replace(have))
	}
	b.WriteString("</table><p class=k>" + escText.Replace(words.T("ingame.summons.prizes_info", nil)) + "</p>")
	return b.String()
}

func thousands(n int32) string {
	s := strconv.Itoa(int(n))
	for i := len(s) - 3; i > 0; i -= 3 {
		s = s[:i] + "," + s[i:]
	}
	return s
}

// prizeBoxLines are the box panel's lines on the summon screen: the first
// four limited prizes, with their stock and how many were drawn.
func prizeBoxLines(prizes []masterdata.Prize, bs store.GachaBannerState) []*pb.GachaOddsItem {
	const shown = 4
	var out []*pb.GachaOddsItem
	for i, p := range prizes {
		if p.Stock <= 0 {
			continue
		}
		if len(out) == shown {
			break
		}
		out = append(out, &pb.GachaOddsItem{
			GachaItem:        &pb.GachaItem{PossessionType: p.Type, PossessionId: p.Id, Count: max(p.Qty, 1), PromotionOrder: int32(len(out) + 1)},
			GachaItemBonus:   &pb.GachaItem{},
			MaxDrawableCount: p.Stock,
			DrewCount:        min(bs.BoxDrewCounts[int32(i)], p.Stock),
			IsTarget:         len(out) == 0, // the top prize
		})
	}
	return out
}

// prizeBoxMode fills a prize box's box panel: its stock lines, single draws,
// and no reset (the stock is shared, not the player's own box).
func prizeBoxMode(g *pb.Gacha, entry store.GachaCatalogEntry, bs *store.GachaBannerState) {
	prizes, ok := masterdata.PrizeBoxFor(entry.GachaId)
	mode, isBox := g.GachaMode.(*pb.Gacha_GachaModeBoxComposition)
	if !ok || !isBox {
		return
	}
	var state store.GachaBannerState
	if bs != nil {
		state = *bs
	}
	mode.GachaModeBoxComposition.PromotionGachaOddsItem = prizeBoxLines(prizes, state)
	mode.GachaModeBoxComposition.IsHideMultipleDrawButton = true
	mode.GachaModeBoxComposition.IsResettableByDrawingAllTargets = false
	mode.GachaModeBoxComposition.IsCurrentBoxResettable = false
}

// eventBoxHTML lists an event summon's boxes for its "i" page: each level's
// prizes (targets in bold), the player's level and what is left in it (the
// game passes the player as userId), and the prizes every level shares.
func eventBoxHTML(r *http.Request, t *gameText, box masterdata.EventSummon) string {
	level, known := int32(0), false
	var bs store.GachaBannerState
	if webUsers != nil {
		if id, err := strconv.ParseInt(r.URL.Query().Get("userId"), 10, 64); err == nil && id > 0 {
			if user, err := webUsers.LoadUser(id); err == nil {
				bs, known = user.Gacha.BannerStates[box.Base], true
				level = gacha.EventLevel(bs)
			}
		}
	}
	esc := html.EscapeString
	words := t.words
	say := func(key string, params map[string]string) string { return escText.Replace(words.T(key, params)) }
	num := func(v int32) string { return words.Number(int64(v)) }
	var b strings.Builder
	b.WriteString("<p class=k>" + say("ingame.summons.levels_info", nil) + "</p>")
	for i, l := range box.Levels {
		n := int32(i + 1)
		head := say("ingame.summons.level", map[string]string{"n": num(n)})
		if known && n == level {
			head = say("ingame.summons.level_yours", map[string]string{"n": num(n)})
		}
		fmt.Fprintf(&b, "<h2>%s</h2><p class=k>%s</p><table>", head, say("ingame.summons.level_info", map[string]string{"percent": percent(words, l.Chance)}))
		for j, p := range l.Items {
			have := words.T("ingame.summons.stock", map[string]string{"n": num(p.Stock)})
			if known && n == level {
				have = words.T("ingame.summons.left", map[string]string{"left": num(gacha.EventPrizeLeft(bs, j, p)), "n": num(p.Stock)})
			}
			name, class := esc(possessionName(t, p.Type, p.Id)), ""
			if p.Target {
				class, have = " class=f", words.T("ingame.summons.target", map[string]string{"have": have})
			}
			fmt.Fprintf(&b, "<tr><td%s>%s ×%s</td><td class=n>%s</td></tr>", class, name, esc(num(max(p.Count, 1))), escText.Replace(have))
		}
		b.WriteString("</table>")
	}
	if shared := masterdata.EventSummonUnlimited(); len(shared) > 0 {
		b.WriteString("<h2>" + say("ingame.summons.shared", nil) + "</h2><p class=k>" + say("ingame.summons.shared_info", nil) + "</p><table>")
		for _, p := range shared {
			fmt.Fprintf(&b, "<tr><td>%s ×%s</td><td class=n>%s</td></tr>", esc(possessionName(t, p.Type, p.Id)), esc(num(max(p.Count, 1))), say("ingame.summons.unlimited", nil))
		}
		b.WriteString("</table>")
	}
	return b.String()
}

// percent is a chance as a percentage number, up to three decimals as the language writes them (0.35: "35").
func percent(words *bunkertext.Texts, f float64) string {
	return strings.TrimRight(strings.TrimRight(words.Decimal(f*100, 3), "0"), ".,")
}
