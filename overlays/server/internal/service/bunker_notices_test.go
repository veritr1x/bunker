package service

import (
	"archive/zip"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/internal/store"
)

// writeNoticePack writes a small notice pack: three notices (one not yet
// published at the test clock) and one image.
func writeNoticePack(t *testing.T) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "notices.zip")
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	z := zip.NewWriter(f)
	index := map[string]any{
		"version": 1,
		"notices": []map[string]any{
			{"id": 10, "type": 3, "title": "Abstract Savior Summons On Now", "publish": 1_000, "thumb": "aa",
				"body": `<section><div class="info-largeimage"><img src="img/aa.webp"></div><h3>Duration</h3><div class="holding-period">Mar. 7</div></section>`},
			{"id": 11, "type": 5, "title": "Known issues", "publish": 2_000, "postscript": 3_000, "body": "<p>Fixed.</p>"},
			{"id": 12, "type": 1, "title": "Ver 9.9 Update", "publish": 9_000, "body": "<p>Later.</p>"},
		},
		"gacha": map[string]int{"613": 10},
	}
	w, _ := z.Create("notices.json")
	json.NewEncoder(w).Encode(index)
	w, _ = z.Create("img/aa.webp")
	w.Write([]byte("RIFF....WEBP"))
	if err := z.Close(); err != nil {
		t.Fatal(err)
	}
	f.Close()
	return path
}

func getNotice(t *testing.T, h http.Handler, url string) (int, string, http.Header) {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, url, nil))
	body, _ := io.ReadAll(rec.Body)
	return rec.Code, string(body), rec.Header()
}

func TestNoticeListShowsPublishedNoticesNewestFirst(t *testing.T) {
	h := NewNotices(writeNoticePack(t), func() int64 { return 5_000 })
	code, page, _ := getNotice(t, h, "/information/")
	if code != 200 {
		t.Fatalf("status %d", code)
	}
	if strings.Contains(page, "Ver 9.9 Update") {
		t.Fatal("a notice published after the game clock is listed")
	}
	// Known issues has a postscript at 3,000, so it sorts above the summon at 1,000.
	if i, j := strings.Index(page, "Known issues"), strings.Index(page, "Abstract Savior"); i < 0 || j < 0 || i > j {
		t.Fatalf("order wrong or missing:\n%s", page)
	}
	if !strings.Contains(page, `href="?informationId=10&amp;tab=update"`) || !strings.Contains(page, `src="img/aa.webp"`) {
		t.Fatalf("row link or thumbnail missing:\n%s", page)
	}
}

func TestNoticeTabsFilterByType(t *testing.T) {
	h := NewNotices(writeNoticePack(t), func() int64 { return 5_000 })
	_, issues, _ := getNotice(t, h, "/information/?tab=bug")
	if !strings.Contains(issues, "Known issues") || strings.Contains(issues, "Abstract Savior") {
		t.Fatalf("Issues tab:\n%s", issues)
	}
	_, events, _ := getNotice(t, h, "/information/?tab=event")
	if strings.Contains(events, "Known issues") || !strings.Contains(events, "Abstract Savior") {
		t.Fatalf("Events tab:\n%s", events)
	}
}

func TestNoticeDetail(t *testing.T) {
	h := NewNotices(writeNoticePack(t), func() int64 { return 5_000 })
	code, page, _ := getNotice(t, h, "/information/?informationId=10&isIngame=1")
	if code != 200 || !strings.Contains(page, "Abstract Savior Summons On Now") || !strings.Contains(page, `class="holding-period"`) || !strings.Contains(page, "Summons Update") {
		t.Fatalf("detail %d:\n%s", code, page)
	}
	code, page, _ = getNotice(t, h, "/information/?informationId=999")
	if code != 404 || !strings.Contains(page, "isn't available") {
		t.Fatalf("unknown notice %d:\n%s", code, page)
	}
}

// The game opens /en/information/ (its language first) with its session in the query.
func TestNoticesUnderTheGameLanguage(t *testing.T) {
	h := NewNotices(writeNoticePack(t), func() int64 { return 5_000 })
	if code, page, _ := getNotice(t, h, "/en/information/?userId=1&isIngame=True&seVolume=0.7"); code != 200 || !strings.Contains(page, "Known issues") {
		t.Fatalf("list %d:\n%s", code, page)
	}
	if code, page, _ := getNotice(t, h, "/en/information/?informationId=10&userId=1"); code != 200 || !strings.Contains(page, "Abstract Savior") {
		t.Fatalf("detail %d:\n%s", code, page)
	}
	if code, _, _ := getNotice(t, h, "/en/information/img/aa.webp"); code != 200 {
		t.Fatalf("image %d", code)
	}
	for path, want := range map[string]bool{"/information/": true, "/en/information/": true, "/en/information": true, "/ja/information/img/a.webp": true,
		"/web/en/gacha-details": false, "/en/informationx": false, "/assets/en/information/": false} {
		if got := IsNoticePath(path); got != want {
			t.Fatalf("IsNoticePath(%q) = %v", path, got)
		}
	}
}

func TestNoticeImages(t *testing.T) {
	h := NewNotices(writeNoticePack(t), func() int64 { return 5_000 })
	code, body, header := getNotice(t, h, "/information/img/aa.webp")
	if code != 200 || body != "RIFF....WEBP" || header.Get("Content-Type") != "image/webp" {
		t.Fatalf("image %d %q %v", code, body, header)
	}
	for _, bad := range []string{"/information/img/../notices.json", "/information/img/zz.webp", "/information/notices.json"} {
		if code, _, _ := getNotice(t, h, bad); code != 404 {
			t.Fatalf("%s: status %d", bad, code)
		}
	}
}

func TestNoticesWithoutPack(t *testing.T) {
	h := NewNotices(filepath.Join(t.TempDir(), "missing.zip"), func() int64 { return 5_000 })
	code, page, _ := getNotice(t, h, "/information/")
	if code != 200 || !strings.Contains(page, "Notices aren't included in this build") {
		t.Fatalf("no pack %d:\n%s", code, page)
	}
	if id := h.GachaNotice(613); id != 0 {
		t.Fatalf("no pack: gacha notice %d", id)
	}
}

func TestGachaNotice(t *testing.T) {
	h := NewNotices(writeNoticePack(t), func() int64 { return 5_000 })
	if id := h.GachaNotice(613); id != 10 {
		t.Fatalf("gacha 613 notice %d", id)
	}
	if id := h.GachaNotice(1); id != 0 {
		t.Fatalf("gacha 1 notice %d", id)
	}
}

func TestSummonLinksToItsNotice(t *testing.T) {
	SetNotices(NewNotices(writeNoticePack(t), func() int64 { return 5_000 }))
	defer SetNotices(nil)
	if g := toProtoGacha(store.GachaCatalogEntry{GachaId: 613}, nil); g.InformationId != 10 {
		t.Fatalf("summon 613 notice %d", g.InformationId)
	}
	if g := toProtoGacha(store.GachaCatalogEntry{GachaId: 1}, nil); g.InformationId != 0 {
		t.Fatalf("summon 1 notice %d", g.InformationId)
	}
}

// The Android launcher points the server at the notices inside the APK
// (assets/notices/) through notices/source.txt instead of copying them out.
func TestNoticesInsideAnotherZip(t *testing.T) {
	inner, err := zip.OpenReader(writeNoticePack(t))
	if err != nil {
		t.Fatal(err)
	}
	defer inner.Close()
	root := t.TempDir()
	apk := filepath.Join(root, "base.apk")
	f, _ := os.Create(apk)
	z := zip.NewWriter(f)
	w, _ := z.Create("classes.dex")
	w.Write([]byte("dex"))
	for _, e := range inner.File {
		r, _ := e.Open()
		w, _ := z.Create("assets/notices/" + e.Name)
		io.Copy(w, r)
		r.Close()
	}
	z.Close()
	f.Close()
	os.MkdirAll(filepath.Join(root, "notices"), 0o755)
	os.WriteFile(filepath.Join(root, "notices", "source.txt"), []byte(apk+"\nassets/notices/\n"), 0o644)

	h := NewNotices(NoticePackPath(root), func() int64 { return 5_000 })
	if code, page, _ := getNotice(t, h, "/information/?informationId=10"); code != 200 || !strings.Contains(page, "Abstract Savior") {
		t.Fatalf("detail %d:\n%s", code, page)
	}
	if code, body, _ := getNotice(t, h, "/information/img/aa.webp"); code != 200 || body != "RIFF....WEBP" {
		t.Fatalf("image %d %q", code, body)
	}
	if code, _, _ := getNotice(t, h, "/information/img/classes.webp"); code != 404 {
		t.Fatalf("entry outside the prefix: %d", code)
	}
}

func TestNoticePackPathPrefersCopiedPack(t *testing.T) {
	root := t.TempDir()
	if p := NoticePackPath(root); p != filepath.Join(root, "notices", "notices.zip") {
		t.Fatalf("default path %q", p)
	}
}

func TestSummonDetailsLinkToTheNotice(t *testing.T) {
	SetNotices(NewNotices(writeNoticePack(t), func() int64 { return 5_000 }))
	defer SetNotices(nil)
	link := summonNoticeHTML(store.GachaCatalogEntry{GachaId: 613})
	if !strings.Contains(link, `href="/en/information/?informationId=10"`) || !strings.Contains(link, "Abstract Savior Summons On Now") || !strings.Contains(link, "<script>") {
		t.Fatalf("link: %s", link)
	}
	if link := summonNoticeHTML(store.GachaCatalogEntry{GachaId: 1}); link != "" {
		t.Fatalf("summon without a notice: %q", link)
	}
}

// The game's "i" button opens a summon's notice when it has one, so the
// notice links on to Bunker's Summons Details page for that summon.
func TestSummonNoticeLinksToSummonsDetails(t *testing.T) {
	h := NewNotices(writeNoticePack(t), func() int64 { return 5_000 })
	_, page, _ := getNotice(t, h, "/en/information/?informationId=10")
	if !strings.Contains(page, `href="/web/en/gacha-details?gachaId=613"`) {
		t.Fatalf("no Summons Details link:\n%s", page)
	}
	_, page, _ = getNotice(t, h, "/en/information/?informationId=11")
	if strings.Contains(page, "gacha-details") {
		t.Fatalf("a notice without a summon links to Summons Details:\n%s", page)
	}
}

// Summons the catalog links to a notice (the paid-only twins) get a Summons
// Details button on it too, beside those the notice pack lists.
func TestCatalogSummonsLinkFromTheirNotice(t *testing.T) {
	h := NewNotices(writeNoticePack(t), func() int64 { return 5_000 })
	h.LinkSummons(map[int32]int32{490: 10, 613: 10})
	_, page, _ := getNotice(t, h, "/en/information/?informationId=10")
	if !strings.Contains(page, "gachaId=490") || strings.Count(page, "gachaId=613") != 1 {
		t.Fatalf("summon links:\n%s", page)
	}
}

// A postscript the game clock hasn't reached yet neither lifts its notice
// to the top nor shows.
func TestFuturePostscriptIsIgnored(t *testing.T) {
	h := NewNotices(writeNoticePack(t), func() int64 { return 2_500 }) // notice 11: published 2,000, postscript 3,000
	_, page, _ := getNotice(t, h, "/information/")
	if strings.Contains(page, "Postscript") {
		t.Fatalf("future postscript shown:\n%s", page)
	}
	h2 := NewNotices(writeNoticePack(t), func() int64 { return 5_000 })
	if _, page, _ := getNotice(t, h2, "/information/"); !strings.Contains(page, "Postscript") {
		t.Fatalf("postscript the clock passed not shown:\n%s", page)
	}
}

func TestNoticeOrderUsesOnlyPastPostscripts(t *testing.T) {
	path := filepath.Join(t.TempDir(), "notices.zip")
	f, _ := os.Create(path)
	z := zip.NewWriter(f)
	w, _ := z.Create("notices.json")
	json.NewEncoder(w).Encode(map[string]any{"version": 1, "notices": []map[string]any{
		{"id": 1, "type": 5, "title": "Known issues", "publish": 1_000, "postscript": 9_000, "body": ""},
		{"id": 2, "type": 1, "title": "Ver 1.1 Update", "publish": 3_000, "body": ""},
	}})
	z.Close()
	f.Close()
	h := NewNotices(path, func() int64 { return 5_000 })
	_, page, _ := getNotice(t, h, "/information/")
	if i, j := strings.Index(page, "Ver 1.1 Update"), strings.Index(page, "Known issues"); i < 0 || j < 0 || i > j {
		t.Fatalf("a notice with a future postscript sorted first:\n%s", page)
	}
}
