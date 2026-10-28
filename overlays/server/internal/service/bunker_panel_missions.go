package service

import (
	"fmt"
	"html"
	"net/http"
	"regexp"
	"strconv"
	"strings"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/missions"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/userdata"
	"lunar-tear/server/internal/utils"
)

// The Anecdotes' panel sheets: the game opens <web base>/web/<language>/panelmission/{sheet}
// (the run's WebviewMissionTargetId) with the player's userId. The page lists
// the run's panels with the player's progress (counted by the missions engine,
// missions/panels.go); a reached panel's reward goes to the gift box, and so
// does the page's own once every panel on it is received. A completed page
// unlocks its story in the Library.

var panelPath = regexp.MustCompile(`^((?:/web/[a-z-]+)?/panelmission/(\d+))(/claim)?$`)

// IsPanelMissionPath says whether path is an Anecdote sheet, its claim, or
// the official page's API.
func IsPanelMissionPath(path string) bool {
	return panelPath.MatchString(path) || panelAPIPath.MatchString(path)
}

type panelUserStore interface {
	LoadUser(userId int64) (store.UserState, error)
	UpdateUser(userId int64, mutate func(*store.UserState)) (store.UserState, error)
}

// Swappable for tests.
var (
	panelSheets = func() *missions.Panels {
		if c := missions.Current(); c != nil {
			return c.Panels
		}
		return nil
	}
	panelUsers panelUserStore
	panelNow   = gametime.NowMillis
)

// giftTextPanelMission: "Earned from panel missions."
const giftTextPanelMission = 25

// SetPanelUsers lets the sheets read and change the player's save, and the
// Library list the pages completed on them.
func SetPanelUsers(u panelUserStore) {
	panelUsers = u
	userdata.PanelPagesDone = func(user *store.UserState) map[int32]int64 {
		if p := panelSheets(); p != nil {
			return p.PagesDone(user)
		}
		return nil
	}
}

func ServePanelMission(w http.ResponseWriter, r *http.Request) {
	if m := panelAPIPath.FindStringSubmatch(r.URL.Path); m != nil {
		servePanelAPI(w, r, m[1])
		return
	}
	if panelWeb != nil && r.Method == http.MethodGet && panelPagePath.MatchString(r.URL.Path) {
		if page, ok := panelWeb.WebPage(); ok {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			w.Header().Set("Cache-Control", "no-store")
			w.Write(page)
			return
		}
	}
	m := panelPath.FindStringSubmatch(r.URL.Path)
	sheet := m[1] // the sheet's path as the game asked for it
	target, _ := strconv.ParseInt(m[2], 10, 32)
	userId, _ := strconv.ParseInt(r.URL.Query().Get("userId"), 10, 64)
	p := panelSheets()
	now := panelNow()
	var run missions.PanelRun
	ok := p != nil && panelUsers != nil
	if ok {
		run, ok = p.Run(int32(target), now)
	}
	if !ok {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Write([]byte(panelHTML("Panel Missions", `<p class="empty">This Anecdote isn't available.</p>`)))
		return
	}
	if m[3] != "" && r.Method == http.MethodPost {
		page, _ := strconv.ParseInt(r.FormValue("page"), 10, 32)
		panel, _ := strconv.ParseInt(r.FormValue("panel"), 10, 32)
		panelUsers.UpdateUser(userId, func(u *store.UserState) {
			rewards, err := p.Claim(u, int32(target), int32(page), int32(panel), now)
			if err != nil {
				return
			}
			for _, rw := range rewards {
				store.AddGift(u, model.PossessionType(rw.Type), rw.Id, rw.Count, giftTextPanelMission, now)
			}
		})
		http.Redirect(w, r, sheet+"?"+r.URL.RawQuery, http.StatusSeeOther)
		return
	}
	u, err := panelUsers.LoadUser(userId)
	if err != nil {
		u = store.UserState{UserId: userId}
	}
	u.Ext.EnsureMaps()
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.Write([]byte(renderPanelSheet(p, run, &u, sheet, r.URL.RawQuery, now)))
}

func renderPanelSheet(p *missions.Panels, run missions.PanelRun, u *store.UserState, sheet, query string, now int64) string {
	sheets := p.Sheets[run.Mission]
	st := p.Progress(u, run)
	text := openGameText()
	defer text.close()
	open := now >= run.Start && (run.End == 0 || now < run.End)
	var b strings.Builder
	fmt.Fprintf(&b, `<div class="period">%s – %s</div>`, day(run.Start), day(run.End))
	if !open {
		b.WriteString(`<p class="note">This Anecdote isn't open now; progress counts while it is.</p>`)
	}
	for _, pg := range sheets.Pages {
		done := st.PageDone[pg.Page] != 0
		fmt.Fprintf(&b, `<h2>SHEET %d%s</h2><div class="grid">`, pg.Page, map[bool]string{true: " · COMPLETE"}[done])
		for i, panel := range pg.Panels {
			key := pg.Page*100 + int32(i)
			have := st.Progress[key]
			cls, action := "panel", ""
			switch {
			case st.Claimed[key]:
				cls += " claimed"
				action = `<span class="got">Received</span>`
			case have >= panel.N && open:
				cls += " ready"
				action = fmt.Sprintf(`<form method="post" action="%s/claim?%s"><input type="hidden" name="page" value="%d"><input type="hidden" name="panel" value="%d"><button>Receive</button></form>`,
					html.EscapeString(sheet), html.EscapeString(query), pg.Page, i)
			}
			note := ""
			if panel.Standin {
				note = `<div class="standin">The original condition isn't recorded; this counts the nearest.</div>`
			}
			fmt.Fprintf(&b, `<div class="%s"><div class="cond">%s</div><div class="bar"><i style="width:%d%%"></i></div><div class="n">%d / %d</div><div class="rw">%s</div>%s%s</div>`,
				cls, html.EscapeString(panel.Text), min(100, int(have*100/max(panel.N, 1))), have, panel.N,
				html.EscapeString(rewardText(text, panel.Rewards)), note, action)
		}
		b.WriteString(`</div>`)
		if len(pg.Complete) > 0 {
			fmt.Fprintf(&b, `<p class="complete">Sheet reward: %s</p>`, html.EscapeString(rewardText(text, pg.Complete)))
		}
		if done {
			if story := panelStory(p, run, pg.Page); story != "" {
				fmt.Fprintf(&b, `<blockquote>%s</blockquote>`, html.EscapeString(story))
			}
		}
	}
	return panelHTML(sheets.Name, b.String())
}

// panelStory is a completed page's story (English), from the game data.
func panelStory(p *missions.Panels, run missions.PanelRun, page int32) string {
	pageId := p.PageId(run.Target, page)
	var flavor int32
	if rows, err := utils.ReadTable[masterdata.EntityMWebviewPanelMissionPage]("m_webview_panel_mission_page"); err == nil {
		for _, r := range rows {
			if r.WebviewPanelMissionPageId == pageId {
				flavor = r.WebviewPanelMissionCompleteFlavorTextId
			}
		}
	}
	if rows, err := utils.ReadTable[masterdata.EntityMWebviewPanelMissionCompleteFlavorText]("m_webview_panel_mission_complete_flavor_text"); err == nil {
		for _, r := range rows {
			if r.WebviewPanelMissionCompleteFlavorTextId == flavor && r.LanguageType == 2 {
				return r.CompleteFlavorText
			}
		}
	}
	return ""
}

func rewardText(t *gameText, rewards []missions.PanelReward) string {
	parts := make([]string, 0, len(rewards))
	for _, r := range rewards {
		parts = append(parts, fmt.Sprintf("%s ×%s", possessionName(t, r.Type, r.Id), thousands(r.Count)))
	}
	return strings.Join(parts, ", ")
}

func possessionName(t *gameText, kind, id int32) string {
	key := ""
	switch model.PossessionType(kind) {
	case model.PossessionTypeFreeGem, model.PossessionTypePaidGem:
		return "Gems"
	case model.PossessionTypeWeapon:
		return t.weaponName(id)
	case model.PossessionTypeCostume:
		return t.costumeName(id)
	case model.PossessionTypeMaterial:
		key = fmt.Sprintf("material.name.%d", id)
	case model.PossessionTypeConsumableItem: // named by its art, not its id
		if rows, err := utils.ReadTable[masterdata.EntityMConsumableItem]("m_consumable_item"); err == nil {
			for _, c := range rows {
				if c.ConsumableItemId == id {
					key = fmt.Sprintf("consumable_item.name.%d%03d", c.AssetCategoryId, c.AssetVariationId)
				}
			}
		}
	case model.PossessionTypeCompanion:
		if rows, err := utils.ReadTable[masterdata.EntityMCompanion]("m_companion"); err == nil {
			for _, c := range rows {
				if c.CompanionId == id {
					key = fmt.Sprintf("companion.name.cm%03d%03d", c.ActorSkeletonId, c.AssetVariationId)
				}
			}
		}
	}
	if name := t.text(key); key != "" && name != "" {
		return name
	}
	return fmt.Sprintf("Item %d", id)
}

// panelClose closes the game's web view: its mission dialog closes on a
// uniwebview:// message with a "close" argument (iOS has no Back key).
const panelClose = `<a class="close" href="uniwebview://panelmission?close=1">CLOSE</a>`

func panelHTML(title, body string) string {
	return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>` +
		html.EscapeString(title) + `</title><style>
body{margin:0;padding:24px 14px 40px;font-family:"Noto Sans",sans-serif;background:#0a0a0f;color:#d4cfc6}
h1{font-size:1.15em;letter-spacing:.12em;color:#e8e0d0;text-align:center;margin:0 0 4px}
h2{font-size:.85em;letter-spacing:.2em;color:#b9b1a2;margin:22px 0 10px}
.period{text-align:center;font-size:.75em;color:#888}
.note,.empty{text-align:center;color:#999;font-size:.8em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.panel{border:1px solid #2c2a26;background:#121218;padding:10px;font-size:.78em;display:flex;flex-direction:column;gap:6px}
.panel.ready{border-color:#8a7a52}.panel.claimed{opacity:.55}
.cond{color:#e3dccf;line-height:1.35}.rw{color:#a99c80}.n{color:#888;font-size:.9em}
.bar{height:4px;background:#24222a}.bar i{display:block;height:100%;background:#a8945f}
.standin{color:#6f6a60;font-size:.85em}
button{background:#a8945f;color:#0a0a0f;border:0;padding:6px 10px;font-weight:bold;letter-spacing:.08em}
.got{color:#a8945f;font-size:.9em}
.complete{color:#a99c80;font-size:.8em}
blockquote{border-left:2px solid #a8945f;margin:12px 0;padding:6px 12px;color:#cfc8ba;font-size:.85em;line-height:1.6}
.close{position:fixed;top:10px;right:12px;color:#d4cfc6;border:1px solid #5a5446;background:#121218;padding:6px 12px;font-size:.8em;letter-spacing:.12em;text-decoration:none}
</style></head><body>` + panelClose + `<h1>` + html.EscapeString(strings.ToUpper(title)) + `</h1>` + body + `</body></html>`
}
