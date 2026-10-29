package service

import (
	"archive/zip"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// writeWebPack writes a notice pack that also carries the official web app
// (web/...): its page, a script and a panel sheet's card.
func writeWebPack(t *testing.T) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "notices.zip")
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	z := zip.NewWriter(f)
	w, _ := z.Create("notices.json")
	json.NewEncoder(w).Encode(map[string]any{"notices": []map[string]any{{"id": 1, "type": 1, "title": "A", "publish": 1}}})
	for name, body := range map[string]string{
		"web/default_page.html":                                 "<!doctype html><title>NieR Re[in]carnation</title>",
		"web/main/main.bundle.js":                               "var app;",
		"web/css/panelmission.bundle.css":                       ".panel{}",
		"web/static/en/subquest/subquest_4.html":                "<h1>Dark Memory</h1>",
		"web/images/en/operations/banner/" + panelFile("guide"): "\xff\xd8\xffGUIDE",
		"web/images/en/operations/panel_mission/8/page1/card/" + panelFile("card_full.jpg"): "\xff\xd8\xffJPEG",
	} {
		w, _ := z.Create(name)
		w.Write([]byte(body))
	}
	if err := z.Close(); err != nil {
		t.Fatal(err)
	}
	f.Close()
	return path
}

// The pack's web app is served at the paths the official page asks for; a
// path it doesn't hold is left to the game's own web server.
func TestNoticePackServesTheWebApp(t *testing.T) {
	n := NewNotices(writeWebPack(t), func() int64 { return 10 })
	for path, want := range map[string]string{
		"/main/main.bundle.js":         "var app;",
		"/css/panelmission.bundle.css": ".panel{}",
		"/images/en/operations/panel_mission/8/page1/card/" + panelFile("card_full.jpg"): "\xff\xd8\xffJPEG",
		// The sub-quest and how-to-play guides' pictures.
		"/images/en/operations/banner/" + panelFile("guide"): "\xff\xd8\xffGUIDE",
		// Another language's page asks for its own images: the pack's English ones.
		"/images/ja/operations/panel_mission/8/page1/card/" + panelFile("card_full.jpg"): "\xff\xd8\xffJPEG",
	} {
		if !n.HasWebFile(path) {
			t.Fatalf("pack lacks %s", path)
		}
		code, body, hdr := getNotice(t, http.HandlerFunc(n.ServeWeb), path)
		if code != 200 || body != want {
			t.Fatalf("%s: %d %q", path, code, body)
		}
		if strings.HasSuffix(path, ".js") && !strings.HasPrefix(hdr.Get("Content-Type"), "text/javascript") {
			t.Fatalf("%s served as %q", path, hdr.Get("Content-Type"))
		}
	}
	if n.HasWebFile("/main/other.js") || n.HasWebFile("/information/") || n.HasWebFile("/notices.json") {
		t.Fatal("served a file the web app doesn't hold")
	}
	page, ok := n.WebPage()
	if !ok || !strings.Contains(string(page), "NieR Re[in]carnation") {
		t.Fatalf("web app page: %q %v", page, ok)
	}
	// A pack without the web app: nothing.
	plain := NewNotices(writeNoticePack(t), func() int64 { return 10 })
	if _, ok := plain.WebPage(); ok || plain.HasWebFile("/main/main.bundle.js") {
		t.Fatal("web app from a pack without one")
	}
}

// The words come in the sheet's order, not the story's; a word the sheet
// shows twice is marked twice.
func TestStoryHTMLMarksEachPanelsWord(t *testing.T) {
	got := storyHTML("It is the never-ending\ntale of the dolls' fight. A tale & a <war>.", []string{"Dolls", "Tale", "never-ending", "Tale", "absent"})
	want := "It is the <span>never-ending</span> <span>tale</span> of the <span>dolls</span>&#39; fight. A <span>tale</span> &amp; a &lt;war&gt;."
	if got != want {
		t.Fatalf("\n got %s\nwant %s", got, want)
	}
}

// The web app's sub-quest guides the game opens, when the pack holds them.
func TestWebAppRoutes(t *testing.T) {
	n := NewNotices(writeWebPack(t), func() int64 { return 10 })
	for target, want := range map[string]bool{
		"/web/en/sub-quest?playguideId=4":  true,
		"/web/en/sub-quest/?playguideId=4": true,
		"/web/en/sub-quest?playguideId=5":  false, // not preserved
		"/web/static/en/terms/termsofuse":  false,
		"/web/en/gacha-details":            false,
	} {
		r := httptest.NewRequest(http.MethodGet, target, nil)
		if got := n.IsWebAppRoute(r); got != want {
			t.Errorf("%s: %v, want %v", target, got, want)
		}
	}
	if !n.HasWebFile("/static/ja/subquest/subquest_4.html") {
		t.Fatal("another language's guide isn't the English one")
	}
	code, body, _ := getNotice(t, http.HandlerFunc(n.ServeWebAppRoute), "/web/en/sub-quest?playguideId=4")
	if code != 200 || !strings.Contains(body, "NieR Re[in]carnation") {
		t.Fatalf("sub-quest page: %d %q", code, body)
	}
}

// A panel's word may be shorter than the story's ("Nightmare" in
// "nightmares", "Wish" in "wished"): the story's word is marked.
func TestStoryHTMLMarksALongerFormOfTheWord(t *testing.T) {
	got := storyHTML("Here, she sees no\nnightmares. The outcome that he has so long wished for.", []string{"Nightmare", "Wish", "Outcome"})
	want := "Here, she sees no <span>nightmares</span>. The <span>outcome</span> that he has so long <span>wished</span> for."
	if got != want {
		t.Fatalf("\n got %s\nwant %s", got, want)
	}
}
