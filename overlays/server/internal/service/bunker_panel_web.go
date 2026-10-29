package service

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"mime"
	"net/http"
	"path"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"lunar-tear/server/internal/missions"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// The Anecdotes' official web page. The notice pack carries the game's web
// app as it was preserved (web/: its page, scripts, styles, sounds and each
// sheet's card and pieces), and the server answers the two calls the panel
// mission page makes: the sheets (/api/wm/panel_mission/pages) and receiving
// a panel (/api/wm/panel_mission/panel/reward). The page posts them to
// /<serverAddress with "-web" after its first part>/api/..., the app's own
// stand-in for api-web.app.nierreincarnation.com.

// webAppPaths are the web app's files the panel mission page loads; a
// language's operations images come from the pack's English ones.
var (
	webAppPath    = regexp.MustCompile(`^/(?:main|css|d_import|audio|ajax|npm|outlink|static|images/common|web/images)/[^?#]+$`)
	webAppImages  = regexp.MustCompile(`^/images/[a-z]{2}(?:-[A-Za-z]+)?/(operations/(?:panel_mission|thumbnail|banner)/[^?#]+)$`)
	panelAPIPath  = regexp.MustCompile(`^/[^/]+/api/wm/panel_mission/(pages|panel/reward)$`)
	panelPagePath = regexp.MustCompile(`^(?:/web/[a-z-]+)?/panelmission/(\d+)$`)
)

// webAppStatic is a page the app loads into itself (a sub-quest's guide, a
// panel mission's how-to-play): the pack's English one.
var webAppStatic = regexp.MustCompile(`^/static/[a-z]{2}(?:-[A-Za-z]+)?/([a-z_]+/[A-Za-z0-9_]+\.html)$`)

func webAppFile(urlPath string) (string, bool) {
	if m := webAppImages.FindStringSubmatch(urlPath); m != nil {
		return "web/images/en/" + m[1], true
	}
	if m := webAppStatic.FindStringSubmatch(urlPath); m != nil {
		return "web/static/en/" + m[1], true
	}
	if webAppPath.MatchString(urlPath) && !strings.Contains(urlPath, "..") {
		return "web" + urlPath, true
	}
	return "", false
}

// HasWebFile says whether the pack holds the web app file urlPath asks for.
func (s *Notices) HasWebFile(urlPath string) bool {
	name, ok := webAppFile(urlPath)
	if !ok || !s.load() {
		return false
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.files[name] != nil
}

// ServeWeb serves a web app file from the pack.
func (s *Notices) ServeWeb(w http.ResponseWriter, r *http.Request) {
	name, ok := webAppFile(r.URL.Path)
	if !ok || !s.load() {
		http.NotFound(w, r)
		return
	}
	s.mu.Lock()
	f := s.files[name]
	s.mu.Unlock()
	if f == nil {
		http.NotFound(w, r)
		return
	}
	rc, err := f.Open()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	defer rc.Close()
	ctype := mime.TypeByExtension(path.Ext(name))
	if ctype == "" { // the cards and pieces are named by hash, without an extension
		head := make([]byte, 512)
		n, _ := io.ReadFull(rc, head)
		head = head[:n]
		ctype = http.DetectContentType(head)
		w.Header().Set("Content-Type", ctype)
		w.Header().Set("Cache-Control", "max-age=86400")
		w.Write(head)
		io.Copy(w, rc)
		return
	}
	w.Header().Set("Content-Type", ctype)
	w.Header().Set("Cache-Control", "max-age=86400")
	io.Copy(w, rc)
}

// WebPage is the web app's page, which shows the panel mission for the URL.
func (s *Notices) WebPage() ([]byte, bool) {
	if !s.load() {
		return nil, false
	}
	s.mu.Lock()
	f := s.files["web/default_page.html"]
	s.mu.Unlock()
	if f == nil {
		return nil, false
	}
	rc, err := f.Open()
	if err != nil {
		return nil, false
	}
	defer rc.Close()
	b, err := io.ReadAll(rc)
	return b, err == nil
}

// The app's other page the game opens: a sub-quest type's guide
// (/web/<lang>/sub-quest?playguideId=N).
var (
	webAppSubQuest = regexp.MustCompile(`^/web/[a-z]{2}(?:-[A-Za-z]+)?/sub-quest/?$`)
	playguideId    = regexp.MustCompile(`^[0-9]+$`)
)

// IsWebAppRoute says whether r is that page and the pack holds its guide.
func (s *Notices) IsWebAppRoute(r *http.Request) bool {
	if !webAppSubQuest.MatchString(r.URL.Path) {
		return false
	}
	id := r.URL.Query().Get("playguideId")
	return playguideId.MatchString(id) && s.HasWebFile("/static/en/subquest/subquest_"+id+".html")
}

// ServeWebAppRoute serves the app's page, which shows the route's content.
func (s *Notices) ServeWebAppRoute(w http.ResponseWriter, r *http.Request) {
	page, ok := s.WebPage()
	if !ok {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.Write(page)
}

type panelWebApp interface {
	WebPage() ([]byte, bool)
}

// panelWeb is the notice pack's web app (SetPanelWeb); without it the
// sheets are Bunker's own page.
var panelWeb panelWebApp

func SetPanelWeb(w panelWebApp) { panelWeb = w }

// panelFile is a sheet image's name in the web app: the SHA-256 of its
// original name (card_full.jpg, card_parts_01.jpg ...).
func panelFile(name string) string {
	h := sha256.Sum256([]byte(name))
	return hex.EncodeToString(h[:])
}

// panelStoryText is a completed page's story; swappable for tests.
var panelStoryText = panelStory

// storyHTML is the story as the page shows it: one paragraph, each panel's
// word in a span. The words come in the sheet's order; each takes its first
// use in the story not already taken (a word shown twice marks two uses).
func storyHTML(story string, words []string) string {
	text := strings.Join(strings.Fields(story), " ")
	type span struct{ at, end int }
	var spans []span
	taken := func(at, end int) bool {
		for _, s := range spans {
			if at < s.end && s.at < end {
				return true
			}
		}
		return false
	}
	mark := func(w string, prefix bool) bool {
		for from := 0; from < len(text); {
			i := wordIndex(text[from:], w, prefix)
			if i < 0 {
				return false
			}
			at := from + i
			end := at + len(w)
			for prefix && end < len(text) && isLetter(text[end]) { // the story's longer form: "nightmares", "wished"
				end++
			}
			if !taken(at, end) {
				spans = append(spans, span{at, end})
				return true
			}
			from = at + 1
		}
		return false
	}
	for _, w := range words {
		if !mark(w, false) {
			mark(w, true)
		}
	}
	sort.Slice(spans, func(i, j int) bool { return spans[i].at < spans[j].at })
	var b strings.Builder
	last := 0
	for _, s := range spans {
		b.WriteString(html.EscapeString(text[last:s.at]))
		b.WriteString("<span>" + html.EscapeString(text[s.at:s.end]) + "</span>")
		last = s.end
	}
	b.WriteString(html.EscapeString(text[last:]))
	return b.String()
}

func isLetter(c byte) bool { return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' }

// wordIndex finds w in s as a whole word, ignoring case; with prefix, as the
// start of a word.
func wordIndex(s, w string, prefix bool) int {
	ls, lw := strings.ToLower(s), strings.ToLower(w)
	for from := 0; ; {
		i := strings.Index(ls[from:], lw)
		if i < 0 {
			return -1
		}
		i += from
		end := i + len(lw)
		if (i == 0 || !isLetter(s[i-1])) && (prefix || end == len(s) || !isLetter(s[end])) {
			return i
		}
		from = i + 1
	}
}

type panelRewardJSON struct {
	RewardType          int32  `json:"rewardType"`
	RewardId            int32  `json:"rewardId"`
	RewardName          string `json:"rewardName"`
	RewardCount         int32  `json:"rewardCount"`
	RewardImageFileName string `json:"rewardImageFileName"`
}

func panelRewardData(t *gameText, r missions.PanelReward) panelRewardJSON {
	return panelRewardJSON{RewardType: r.Type, RewardId: r.Id, RewardName: possessionName(t, r.Type, r.Id), RewardCount: r.Count,
		RewardImageFileName: fmt.Sprintf("%d.png", r.Id)}
}

// panelRequest is the page's request body; webviewMissionId is the route's
// string on the first call and a number after.
type panelRequest struct {
	CommonRequest struct {
		UserIdString string `json:"userIdString"`
	} `json:"commonRequest"`
	WebviewMissionId json.Number `json:"webviewMissionId"`
	Page             int32       `json:"page"`
	PositionId       int32       `json:"positionId"`
}

func panelError(w http.ResponseWriter, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusBadRequest)
	json.NewEncoder(w).Encode(map[string]any{"commonResponse": map[string]any{"messageCode": code}})
}

func servePanelAPI(w http.ResponseWriter, r *http.Request, call string) {
	var req panelRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		panelError(w, 199999)
		return
	}
	userId, _ := strconv.ParseInt(req.CommonRequest.UserIdString, 10, 64)
	target, _ := strconv.ParseInt(req.WebviewMissionId.String(), 10, 32)
	p := panelSheets()
	now := panelNow()
	var run missions.PanelRun
	ok := p != nil && panelUsers != nil
	if ok {
		run, ok = p.Run(int32(target), now)
	}
	if !ok {
		panelError(w, 199999)
		return
	}
	text := openGameText()
	defer text.close()
	var data any
	if call == "pages" {
		u, err := panelUsers.LoadUser(userId)
		if err != nil {
			u = store.UserState{UserId: userId}
		}
		u.Ext.EnsureMaps()
		data = panelPagesData(p, run, &u, text, now)
	} else {
		var rewards []missions.PanelReward
		var claimErr error
		panelUsers.UpdateUser(userId, func(u *store.UserState) {
			rewards, claimErr = p.Claim(u, run.Target, req.Page, req.PositionId-1, now)
			if claimErr != nil {
				return
			}
			for _, rw := range rewards {
				store.AddGift(u, model.PossessionType(rw.Type), rw.Id, rw.Count, giftTextPanelMission, now)
			}
		})
		switch claimErr {
		case nil:
		case missions.ErrClaimed:
			panelError(w, 292016) // the page shows the panel as opened
			return
		default:
			panelError(w, 199999)
			return
		}
		pg := panelPage(p, run, req.Page)
		panel := pg.Panels[req.PositionId-1]
		out := map[string]any{"reward": panelRewardData(text, panel.Rewards[0]), "isComplete": len(rewards) > len(panel.Rewards)}
		if out["isComplete"] == true {
			list := make([]panelRewardJSON, 0, len(pg.Complete))
			for _, rw := range pg.Complete {
				list = append(list, panelRewardData(text, rw))
			}
			out["pageData"] = map[string]any{"imageFileName": panelFile("card_full.jpg"),
				"compFlavorText": storyHTML(panelStoryText(p, run, req.Page), pg.Words), "rewardList": list}
		}
		data = out
	}
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	json.NewEncoder(w).Encode(map[string]any{"data": data})
}

func panelPage(p *missions.Panels, run missions.PanelRun, page int32) *missions.PanelPage {
	for i := range p.Sheets[run.Mission].Pages {
		if pg := &p.Sheets[run.Mission].Pages[i]; pg.Page == page {
			return pg
		}
	}
	return nil
}

func panelPagesData(p *missions.Panels, run missions.PanelRun, u *store.UserState, text *gameText, now int64) map[string]any {
	sheets := p.Sheets[run.Mission]
	st := p.Progress(u, run)
	termOver := run.End != 0 && now >= run.End
	pages := []map[string]any{}
	all := true
	for _, pg := range sheets.Pages {
		done := st.PageDone[pg.Page] != 0
		all = all && done
		parts := make([]map[string]any, 0, len(pg.Parts))
		for i, part := range pg.Parts {
			parts = append(parts, map[string]any{"bgPartsIndex": i + 1, "imagePath": panelFile(fmt.Sprintf("card_parts_%02d.jpg", i+1)),
				"transform": map[string]any{"moveBeforeX": part[0], "moveBeforeY": part[1], "rotate": part[2], "moveType": part[3]}})
		}
		panels := make([]map[string]any, 0, len(pg.Panels))
		for i, panel := range pg.Panels {
			key := pg.Page*100 + int32(i)
			status := 1 // in progress
			switch {
			case st.Claimed[key]:
				status = 3
			case st.Progress[key] >= panel.N:
				status = 2
			}
			word := ""
			if i < len(pg.Words) {
				word = pg.Words[i]
			}
			panels = append(panels, map[string]any{"positionId": i + 1, "panelGroupId": p.PageId(run.Target, pg.Page),
				"title": panel.Text, "longTitle": panel.Text, "flavorText": word, "conditions": []string{}, "lockText": "",
				"panelMissionProgressStatusType": status, "numerator": min(st.Progress[key], panel.N), "denominator": panel.N,
				"reward": panelRewardData(text, panel.Rewards[0])})
		}
		page := map[string]any{"pageNumber": pg.Page, "isComplete": done, "isTermOver": termOver,
			"imageFileName": panelFile("card_full.jpg"), "bgParts": parts, "panels": panels,
			"compFlavorText": storyHTML(panelStoryText(p, run, pg.Page), pg.Words)}
		pages = append(pages, page)
	}
	return map[string]any{"webviewMissionId": run.Mission, "webviewPanelMissionId": run.Mission, "eventTitle": sheets.Name,
		"startDate": run.Start, "endDate": run.End, "isAllComplete": all, "pages": pages}
}
