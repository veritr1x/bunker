package service

import (
	"fmt"
	"html"
	"net/http"
	"strconv"
	"strings"

	pb "lunar-tear/server/gen/proto"
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
func prizeSectionHTML(r *http.Request, gachaId int32, prizes []masterdata.Prize) string {
	var left []int32
	if webUsers != nil {
		if id, err := strconv.ParseInt(r.URL.Query().Get("userId"), 10, 64); err == nil && id > 0 {
			if user, err := webUsers.LoadUser(id); err == nil {
				bs := user.Gacha.BannerStates[gachaId]
				left = gacha.PrizesLeft(&bs, prizes)
			}
		}
	}
	var b strings.Builder
	b.WriteString("<h2>PRIZES</h2><table>")
	for i, p := range prizes {
		have := "unlimited"
		if p.Stock > 0 {
			have = "stock " + thousands(p.Stock)
			if left != nil {
				have = fmt.Sprintf("%s of %s left", thousands(left[i]), thousands(p.Stock))
			}
		}
		fmt.Fprintf(&b, "<tr><td>%s ×%s</td><td class=n>%s</td></tr>", html.EscapeString(p.Name), thousands(p.Qty), have)
	}
	b.WriteString("</table><p class=k>Each draw gives one prize; a limited prize is drawn by how many are left.</p>")
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
