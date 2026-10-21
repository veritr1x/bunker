package service

import (
	"archive/zip"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"

	"lunar-tear/server/internal/store"
)

// Notices serves the game's Notices screen (/information/) from Bunker's
// notice pack: a zip holding notices.json and img/<key>.webp, built from the
// official notices recovered from archives. The game opens /information/ for
// the list and /information/?informationId=N for one notice. Notices appear
// once the game clock reaches their publish date, so with the Original
// calendar they come out as they did in the live game.
type Notices struct {
	path string
	now  func() int64

	mu     sync.Mutex
	loaded bool
	zip    *zip.ReadCloser
	files  map[string]*zip.File
	list   []*notice
	byID   map[int32]*notice
	gacha  map[int32]int32   // summon -> its notice
	summon map[int32][]int32 // notice -> its summons
}

type notice struct {
	Id         int32  `json:"id"`
	Type       int32  `json:"type"`
	Title      string `json:"title"`
	Publish    int64  `json:"publish"`
	Postscript int64  `json:"postscript"`
	Thumb      string `json:"thumb"`
	Body       string `json:"body"`
}

func (n *notice) sortTime() int64 {
	if n.Postscript > n.Publish {
		return n.Postscript
	}
	return n.Publish
}

// NoticePackPath finds the notice pack under assetRoot: notices/notices.zip,
// or else the place notices/source.txt names (a zip and the folder inside it
// holding the pack: the Android launcher points at assets/notices/ in the
// game's own APK rather than copying it out).
func NoticePackPath(assetRoot string) string {
	dir := filepath.Join(assetRoot, "notices")
	copied := filepath.Join(dir, "notices.zip")
	if _, err := os.Stat(copied); err == nil {
		return copied
	}
	if b, err := os.ReadFile(filepath.Join(dir, "source.txt")); err == nil {
		lines := strings.Split(strings.TrimSpace(string(b)), "\n")
		if lines[0] != "" {
			if len(lines) > 1 && strings.TrimSpace(lines[1]) != "" {
				return lines[0] + "!" + strings.TrimSpace(lines[1])
			}
			return lines[0]
		}
	}
	return copied
}

// NewNotices serves the pack at path ("file.zip", or "file.zip!folder/" for a
// pack inside a larger zip); now gives the game clock in Unix ms.
func NewNotices(path string, now func() int64) *Notices {
	return &Notices{path: path, now: now}
}

// load opens the pack on first use. A missing or broken pack is retried on
// the next request, so a pack copied in later is picked up.
func (s *Notices) load() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.loaded {
		return true
	}
	zipPath, prefix, _ := strings.Cut(s.path, "!")
	z, err := zip.OpenReader(zipPath)
	if err != nil {
		return false
	}
	files := map[string]*zip.File{}
	for _, f := range z.File {
		if name, ok := strings.CutPrefix(f.Name, prefix); ok {
			files[name] = f
		}
	}
	var index struct {
		Notices []*notice        `json:"notices"`
		Gacha   map[string]int32 `json:"gacha"`
	}
	if f := files["notices.json"]; f != nil {
		if r, err := f.Open(); err == nil {
			err = json.NewDecoder(r).Decode(&index)
			r.Close()
			if err != nil {
				log.Printf("[Notices] %s: %v", s.path, err)
			}
		}
	}
	if len(index.Notices) == 0 {
		z.Close()
		return false
	}
	s.zip, s.files, s.list = z, files, index.Notices
	s.byID = make(map[int32]*notice, len(index.Notices))
	for _, n := range index.Notices {
		s.byID[n.Id] = n
	}
	sort.SliceStable(s.list, func(i, j int) bool { return s.list[i].sortTime() > s.list[j].sortTime() })
	s.gacha, s.summon = map[int32]int32{}, map[int32][]int32{}
	for k, v := range index.Gacha {
		if id, err := strconv.Atoi(k); err == nil {
			s.gacha[int32(id)] = v
			s.summon[v] = append(s.summon[v], int32(id))
		}
	}
	for _, ids := range s.summon {
		sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	}
	s.loaded = true
	log.Printf("[Notices] %d notices from %s", len(s.list), s.path)
	return true
}

// GachaNotice is the notice that announced a summon, or 0.
func (s *Notices) GachaNotice(gachaId int32) int32 {
	if !s.load() {
		return 0
	}
	return s.gacha[gachaId]
}

// noticePath matches the Notices pages under the game's language
// (/en/information/), or without one.
var noticePath = regexp.MustCompile(`^(?:/[a-z]{2}(?:-[A-Za-z]+)?)?/information(/.*)?$`)
var noticeImage = regexp.MustCompile(`^/img/([A-Za-z0-9_-]+)\.webp$`)

// IsNoticePath says whether path belongs to the Notices pages.
func IsNoticePath(path string) bool { return noticePath.MatchString(path) }

func (s *Notices) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	m := noticePath.FindStringSubmatch(r.URL.Path)
	if m == nil {
		http.NotFound(w, r)
		return
	}
	if img := noticeImage.FindStringSubmatch(m[1]); img != nil {
		s.serveImage(w, img[1])
		return
	}
	if m[1] != "" && m[1] != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	if !s.load() {
		w.Write([]byte(noticePage("Notices", `<p class="empty">Notices aren't included in this build.</p>`)))
		return
	}
	q := r.URL.Query()
	if id := q.Get("informationId"); id != "" {
		s.serveDetail(w, id, q.Get("tab"))
		return
	}
	s.serveList(w, q.Get("tab"))
}

func (s *Notices) serveImage(w http.ResponseWriter, key string) {
	if !s.load() {
		w.WriteHeader(http.StatusNotFound)
		return
	}
	f := s.files["img/"+key+".webp"]
	if f == nil {
		w.WriteHeader(http.StatusNotFound)
		return
	}
	rc, err := f.Open()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}
	defer rc.Close()
	w.Header().Set("Content-Type", "image/webp")
	w.Header().Set("Content-Length", strconv.FormatUint(f.UncompressedSize64, 10))
	w.Header().Set("Cache-Control", "max-age=31536000, immutable")
	io.Copy(w, rc)
}

// The game's three tabs: News (everything), Events and Issues.
var noticeTabs = []struct {
	key, label string
	types      map[int32]bool
}{
	{"update", "News", nil},
	{"event", "Events", map[int32]bool{1: true, 2: true, 3: true, 4: true, 11: true}},
	{"bug", "Issues", map[int32]bool{5: true}},
}

// noticeBadge is the label and colour the game gave each notice type.
func noticeBadge(t int32) (string, string) {
	switch t {
	case 1:
		return "Update", "light"
	case 2:
		return "Event", "light"
	case 3:
		return "Summons Update", "light"
	case 4:
		return "Campaign", "light"
	case 5:
		return "Issue", "red"
	case 6:
		return "Maintenance", "red"
	case 7:
		return "Information", "dark"
	case 9:
		return "Operation Letter", "dark"
	case 11:
		return "Mission", "light"
	}
	return "Other", "dark"
}

func badgeHTML(t int32) string {
	label, tone := noticeBadge(t)
	return `<span class="badge ` + tone + `">` + label + `</span>`
}

func dateHTML(n *notice) string {
	s := `<time data-ms="` + strconv.FormatInt(n.Publish, 10) + `"></time>`
	if n.Postscript > 0 {
		s += ` <span class="post">[Postscript: <time data-ms="` + strconv.FormatInt(n.Postscript, 10) + `"></time>]</span>`
	}
	return s
}

func tabIndex(key string) int {
	for i, t := range noticeTabs {
		if t.key == key {
			return i
		}
	}
	return 0
}

func tabsHTML(current int) string {
	var b strings.Builder
	b.WriteString(`<nav class="tabs">`)
	for i, t := range noticeTabs {
		cls := ""
		if i == current {
			cls = ` class="on"`
		}
		fmt.Fprintf(&b, `<a%s href="?tab=%s">%s</a>`, cls, t.key, t.label)
	}
	b.WriteString(`</nav>`)
	return b.String()
}

func (s *Notices) serveList(w http.ResponseWriter, tabKey string) {
	tab := tabIndex(tabKey)
	now := s.now()
	var b strings.Builder
	b.WriteString(tabsHTML(tab))
	b.WriteString(`<main class="list">`)
	shown := 0
	for _, n := range s.list {
		if n.Publish > now || (noticeTabs[tab].types != nil && !noticeTabs[tab].types[n.Type]) {
			continue
		}
		shown++
		thumb := ""
		if n.Thumb != "" {
			thumb = `<img class="thumb" loading="lazy" src="img/` + n.Thumb + `.webp" alt="">`
		}
		fmt.Fprintf(&b, `<a class="row" href="?informationId=%d&amp;tab=%s"><div class="row-head">%s<span class="date">%s</span></div><div class="row-body">%s<span class="title">%s</span></div><span class="arrow"></span></a>`,
			n.Id, noticeTabs[tab].key, badgeHTML(n.Type), dateHTML(n), thumb, html.EscapeString(n.Title))
	}
	if shown == 0 {
		b.WriteString(`<p class="empty">There are no notices yet.</p>`)
	}
	b.WriteString(`</main>`)
	w.Write([]byte(noticePage("Notices", b.String())))
}

func (s *Notices) serveDetail(w http.ResponseWriter, id, tabKey string) {
	tab := tabIndex(tabKey)
	v, _ := strconv.Atoi(id)
	n := s.byID[int32(v)]
	if n == nil {
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte(noticePage("Notices", tabsHTML(tab)+`<main><a class="back" href="?tab=`+noticeTabs[tab].key+`" aria-label="Back"></a><p class="empty">This notice isn't available.</p></main>`)))
		return
	}
	// Bunker's Summons Details (costs, exchange, pool) for the summons this notice announced.
	var details strings.Builder
	for _, g := range s.summon[n.Id] {
		fmt.Fprintf(&details, `<a class="other-link-btn" href="/web/en/gacha-details?gachaId=%d">Summons Details</a>`, g)
	}
	body := fmt.Sprintf(`%s<main class="detail"><header><a class="back" href="?tab=%s" aria-label="Back"></a><div class="head-text">%s<h1>%s</h1></div><span class="date">%s</span></header><article>%s%s</article></main>`,
		tabsHTML(tab), noticeTabs[tab].key, badgeHTML(n.Type), html.EscapeString(n.Title), dateHTML(n), details.String(), n.Body)
	w.Write([]byte(noticePage(n.Title, body)))
}

func noticePage(title, body string) string {
	return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover"><title>` +
		html.EscapeString(title) + `</title><style>` + noticeCSS + `</style></head><body>` + body + `<script>` + noticeJS + `</script></body></html>`
}

// noticeJS shows dates in the device's time zone, as the game did, and opens
// notices in place: the game's web view hands any page load from a tapped
// link to the system browser, so links fetch the next page and swap it in
// (with the page's own history for Back), as the original notice app did.
const noticeJS = `
(function(){
var pad=function(n){return (n<10?'0':'')+n};
function dates(){document.querySelectorAll('time[data-ms]').forEach(function(t){var d=new Date(+t.dataset.ms);
t.textContent=pad(d.getMonth()+1)+'/'+pad(d.getDate())+'/'+d.getFullYear()+' '+pad(d.getHours())+':'+pad(d.getMinutes())})}
function show(url,push,y){
  fetch(url,{cache:'no-store'}).then(function(r){return r.text()}).then(function(text){
    var page=new DOMParser().parseFromString(text,'text/html');
    if(push){history.replaceState({y:window.scrollY,n:(history.state&&history.state.n)||0},'');history.pushState({y:0,n:((history.state&&history.state.n)||0)+1},'',url)}
    document.title=page.title;document.head.innerHTML=page.head.innerHTML;document.body.innerHTML=page.body.innerHTML;dates();window.scrollTo(0,y||0);
  }).catch(function(){});
}
document.addEventListener('click',function(e){
  var a=e.target.closest('a[href]'),b=e.target.closest('[data-informationid]');
  if(a){e.preventDefault();
    if(a.classList.contains('back')&&history.state&&history.state.n>0){history.back();return}
    show(a.getAttribute('href'),true);return}
  if(b&&/^\d+$/.test(b.dataset.informationid))show('?informationId='+b.dataset.informationid,true);
});
window.addEventListener('popstate',function(e){show(location.href,false,e.state&&e.state.y)});
dates();
})();
`

const noticeCSS = `
:root{--ink:#dbd6c5;--dim:#a39c90;--pink:#d29797;--bar:#c1bdae;--bar-ink:#4b4341;--line:#736b68;--panel:#2b2625;--panel-2:#332e2d;--tab:#736b68;--tab-on:#e3dfcc;--bg:#1b1918;color-scheme:dark}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.65 "Noto Sans","Hiragino Sans",system-ui,sans-serif;-webkit-text-size-adjust:100%}
a{color:inherit;text-decoration:none}
img{max-width:100%}
.tabs{position:sticky;top:0;z-index:5;display:flex;gap:2px;padding:6px 8px 7px;background:var(--bg);border-bottom:1px solid var(--line)}
.tabs a{flex:1;text-align:center;font-weight:700;font-size:13px;line-height:22px;background:var(--tab);color:#e6e2cf;clip-path:polygon(8px 0,calc(100% - 8px) 0,100% 50%,calc(100% - 8px) 100%,8px 100%,0 50%);box-shadow:inset 0 0 0 1px #b3b0a1}
.tabs a.on{background:var(--tab-on);color:var(--line)}
main{padding:8px 8px 32px}
.empty{color:var(--dim);text-align:center;margin:48px 0}
.badge{display:inline-block;min-width:112px;padding:0 14px;font-size:11px;font-weight:700;line-height:18px;text-align:center;white-space:nowrap;clip-path:polygon(0 0,calc(100% - 7px) 0,100% 50%,calc(100% - 7px) 100%,0 100%)}
.badge.light{background:#e6dfcf;color:#736b68}
.badge.red{background:var(--pink);color:#362e2d}
.badge.dark{background:#3b3433;color:var(--ink);box-shadow:inset 0 0 0 1px #8a817c}
.row{position:relative;display:block;margin-bottom:6px;padding:4px 26px 8px 6px;background:linear-gradient(135deg,rgba(255,255,255,.03) 25%,transparent 25%,transparent 50%,rgba(255,255,255,.03) 50%,rgba(255,255,255,.03) 75%,transparent 75%) 0 0/24px 24px,var(--panel);border:1px solid #4a4240;border-top-color:#5d5452}
.row:active{filter:brightness(1.15)}
.row-head{display:flex;justify-content:space-between;align-items:center;gap:8px}
.date{color:var(--ink);font-size:11px;white-space:nowrap}
.post{color:var(--pink)}
.row-body{display:flex;gap:10px;align-items:flex-start;margin-top:6px}
.thumb{width:108px;height:55px;object-fit:cover;object-position:left center;border:1px solid #8a817c;flex:none;background:#000}
.title{color:var(--pink);font-weight:700;font-size:14px;line-height:1.4}
.arrow{position:absolute;top:0;right:0;bottom:0;width:16px;background:var(--line)}
.arrow:after{content:"";position:absolute;top:50%;left:4px;width:6px;height:6px;margin-top:-4px;border:solid #e6e2cf;border-width:2px 2px 0 0;transform:rotate(45deg)}
.detail header{display:flex;gap:10px;align-items:flex-start;padding-bottom:10px;margin-bottom:12px;border-bottom:1px solid var(--line)}
.back{display:block;flex:none;width:36px;height:36px;border:2px solid var(--line);outline:1px solid #4b4341;background:#2b2625;position:relative}
.back:after{content:"";position:absolute;left:12px;top:11px;width:10px;height:10px;border:solid var(--ink);border-width:0 0 3px 3px;transform:rotate(45deg)}
main > .back{margin-bottom:8px}
.head-text{flex:1;min-width:0}
h1{margin:4px 0 0;font-size:15px;line-height:1.4;color:var(--ink)}
article{overflow-wrap:anywhere}
article section{margin-bottom:6px}
article p{margin:0 0 8px}
article .info-largeimage{margin:0 0 10px}
article .info-largeimage img{display:block;width:100%;border:1px solid #8a817c}
article img.stand-in{max-width:640px;margin:0 auto}
article h2{text-align:center;font-size:13px;margin:22px 0 12px;padding:2px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
article h3{position:relative;margin:26px 0 12px;padding:3px 10px 2px 12px;font-size:12px;line-height:16px;background:var(--bar);color:var(--bar-ink)}
article h3:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--bar-ink)}
article h4{margin:10px 0 6px;padding:0 0 1px 14px;font-size:12px;border-bottom:1px solid #423b3a;position:relative}
article h4:before{content:"";position:absolute;left:1px;top:6px;width:7px;height:7px;background:var(--bar);transform:rotate(45deg)}
article h5{margin:6px 0 4px;font-size:12px;background:var(--bar-ink);border:1px solid var(--line);padding:0 6px}
article h6{margin:4px 0;font-size:11px;border-bottom:1px solid var(--bar-ink)}
article ul{margin:4px 0 8px;padding-left:18px}
.text-red{color:var(--pink)}
.al-center{text-align:center!important}
.holding-period{text-align:center;padding:6px 0 5px;margin:4px 0;background:linear-gradient(90deg,transparent,rgba(115,107,104,.55) 25%,rgba(115,107,104,.55) 75%,transparent)}
.information_table{margin:8px 0 14px;overflow-x:auto}
article table{border-collapse:collapse;font-size:12px}
article th{background:var(--bar-ink);color:var(--ink);text-align:left;padding:2px 6px;border:1px solid var(--line)}
article td{border:1px solid var(--line);padding:2px 6px;vertical-align:middle}
article td img,article .weapon_icon,article .coin_icon{vertical-align:middle;max-height:48px}
article .gem_icon{height:16px;vertical-align:-3px}
article img.star,article .star img{width:12px;vertical-align:-1px}
article .status_icon{width:12px;margin-right:4px;vertical-align:-1px}
.attention_content{color:var(--dim);font-size:12px}
.other-link-btn{display:block;width:fit-content;max-width:100%;margin:12px auto;padding:3px 26px;background:#e6dfcf;color:#736b68;font-size:12px;font-weight:700;text-align:center;cursor:pointer;clip-path:polygon(10px 0,calc(100% - 10px) 0,100% 50%,calc(100% - 10px) 100%,10px 100%,0 50%)}
.pickup_character-content,.pickup_weapon-content{border:1px solid var(--line);background:var(--panel-2);margin:8px 0;padding:6px}
.pickup_character-content > div,.pickup_weapon-content > div{display:flex;flex-wrap:wrap;gap:8px}
.pickup_character-chara_image_area{position:relative;flex:0 1 336px}
.pickup_character-status_area{flex:1 1 260px;min-width:0}
.chara_profile{background:#b3b0a1;border:2px solid var(--line);color:var(--bar-ink);padding:2px 4px}
.character_name{background:var(--line);color:#e6e2cf;padding:0 4px;margin:0 4px;font-size:11px}
.awakening_icon{width:20px;vertical-align:middle}
.switch_button{display:none}
.type-a ul{list-style:none;padding:0;display:flex;flex-wrap:wrap;border-top:1px solid var(--line);border-left:1px solid var(--line)}
.type-a li{width:50%;border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:0 6px;font-size:11px;display:flex;align-items:center}
.status-value{margin-left:auto}
.skill_profile-block{display:flex;gap:8px;padding:4px 6px;border:1px solid var(--line);border-top:none}
.skill_icon,.skill_icon img{width:32px;height:32px;flex:none}
.skill_detile{flex:1;min-width:0}
.description{font-size:11px;line-height:1.35;color:var(--ink)}
.recast_time{background:var(--line);padding:0 4px;font-size:10px}
.mama_balloon{display:flex;gap:8px;align-items:flex-start;margin:8px 0}
.mama_img{width:56px;flex:none}
.balloon{background:#e6dfcf;color:var(--bar-ink);padding:6px 10px;border-radius:10px}
`

var (
	activeNoticesMu sync.RWMutex
	activeNotices   *Notices
)

// SetNotices makes summons link to their notices from this pack (nil: none).
func SetNotices(n *Notices) {
	activeNoticesMu.Lock()
	activeNotices = n
	activeNoticesMu.Unlock()
}

// summonNoticeHTML links Summons Details (the summon's "i" page) to the
// summon's notice, opened in place like the notices themselves; "" if none.
func summonNoticeHTML(entry store.GachaCatalogEntry) string {
	id := summonNotice(entry)
	activeNoticesMu.RLock()
	n := activeNotices
	activeNoticesMu.RUnlock()
	if id == 0 || n == nil {
		return ""
	}
	title := n.Title(id)
	if title == "" {
		return ""
	}
	return fmt.Sprintf(`<p><a class="notice-link" href="/en/information/?informationId=%d">Notice: %s</a></p><script>%s</script>`,
		id, html.EscapeString(title), noticeJS)
}

// Title is a notice's title, or "" if the pack doesn't have it.
func (s *Notices) Title(id int32) string {
	if !s.load() {
		return ""
	}
	if n := s.byID[id]; n != nil {
		return n.Title
	}
	return ""
}

// summonNotice is the notice id the game opens from a summon's page.
func summonNotice(entry store.GachaCatalogEntry) int32 {
	if entry.InformationId != 0 {
		return entry.InformationId
	}
	activeNoticesMu.RLock()
	n := activeNotices
	activeNoticesMu.RUnlock()
	if n == nil {
		return 0
	}
	return n.GachaNotice(entry.GachaId)
}
