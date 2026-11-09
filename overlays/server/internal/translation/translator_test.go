package translation

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"testing"
)

const uiID, giftID = "vqZsA7", "i9kb1A"

type roots struct{ asset, data string }

// newRoots is an assetRoot with the sample list.bin and two text bundles in
// the shared tree, and an empty dataRoot.
func newRoots(t *testing.T) roots { return newRootsIn(t, "") }

// newRootsIn puts them in a platform's tree (revisions/0/<platform>/…) instead.
func newRootsIn(t *testing.T, platform string) roots {
	r := roots{asset: t.TempDir(), data: t.TempDir()}
	rev := filepath.Join(r.asset, "assets/revisions/0", platform)
	list, _ := sampleList()
	for path, data := range map[string][]byte{
		"list.bin":                             list,
		"assetbundle/text/en/ui.assetbundle":   []byte("ui"),
		"assetbundle/text/en/gift.assetbundle": []byte("gift"),
	} {
		file := filepath.Join(rev, path)
		os.MkdirAll(filepath.Dir(file), 0755)
		if err := os.WriteFile(file, data, 0644); err != nil {
			t.Fatal(err)
		}
	}
	return r
}

func (r roots) setPack(t *testing.T, word string) {
	content := `{"format":1,"language":"pt","game":{"k":"` + word + `"}}`
	if err := writeFileAtomic(filepath.Join(r.asset, "translation/active.json"), []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
}

func (r roots) removePack(t *testing.T) {
	if err := os.Remove(filepath.Join(r.asset, "translation/active.json")); err != nil {
		t.Fatal(err)
	}
}

// translateUI changes only the ui bundle, to "UI:<translation of k>".
func translateUI(raw []byte, name string, values map[string]string) ([]byte, uint32, bool, error) {
	if name != "text)en)ui" {
		return nil, 0, false, nil
	}
	return []byte("UI:" + values["k"]), 9, true, nil
}

// next stands for the CDN: the list file for list paths, "ORIGINAL" for anything else.
func next(r roots) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		if isListPath(req.URL.Path) {
			data, err := os.ReadFile(filepath.Join(r.asset, "assets/revisions/0/list.bin"))
			for _, platform := range []string{"android", "ios"} {
				if err != nil {
					data, err = os.ReadFile(filepath.Join(r.asset, "assets/revisions/0", platform, "list.bin"))
				}
			}
			w.Header().Set("Content-Type", "application/x-protobuf")
			w.Write(data)
			return
		}
		io.WriteString(w, "ORIGINAL")
	})
}

func start(t *testing.T, r roots, rebuild Rebuilder) *Translator {
	return startOn(t, r, "android", rebuild)
}

func startOn(t *testing.T, r roots, platform string, rebuild Rebuilder) *Translator {
	tr := New(r.asset, r.data, platform)
	tr.rebuild = rebuild
	tr.Start()
	return tr
}

func get(t *testing.T, h http.Handler, path string) []byte {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", path, nil))
	if rec.Code != 200 {
		t.Fatalf("%s: status %d", path, rec.Code)
	}
	body := rec.Body.Bytes()
	if n := rec.Header().Get("Content-Length"); n != "" && n != strconv.Itoa(len(body)) {
		t.Fatalf("%s: Content-Length %s for %d bytes", path, n, len(body))
	}
	return body
}

func listOf(t *testing.T, body []byte) (uint64, map[string]Entry) {
	t.Helper()
	revision, entries, err := ParseList(body)
	if err != nil {
		t.Fatal(err)
	}
	byID := map[string]Entry{}
	for _, e := range entries {
		byID[e.ObjectID] = e
	}
	return revision, byID
}

const listURL = "/v1/list/300116832/817"
const uiURL = "/rrrrr/unso-1-assetbundle/" + uiID + "?generation=1&alt=media"

func TestNoPackPassesThrough(t *testing.T) {
	r := newRoots(t)
	tr := start(t, r, translateUI)
	tr.wait()
	original, _ := sampleList()
	if body := get(t, tr.Wrap(next(r)), listURL); !bytes.Equal(body, original) {
		t.Fatal("list changed")
	}
	if _, err := os.Stat(filepath.Join(r.data, "translation-state.json")); !os.IsNotExist(err) {
		t.Fatal("state file created")
	}
}

func TestPackServesTranslatedList(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	tr := start(t, r, translateUI)
	tr.wait()
	revision, entries := listOf(t, get(t, tr.Wrap(next(r)), listURL))
	if revision != 1817 || entries[uiID].Size != 5 || entries[uiID].CRC != 9 {
		t.Fatalf("revision %d ui %+v", revision, entries[uiID])
	}
	if entries[giftID].Size != 1692 {
		t.Fatalf("gift changed: %+v", entries[giftID])
	}
}

func TestTranslatedAssetServed(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	tr := start(t, r, translateUI)
	tr.wait()
	h := tr.Wrap(next(r))
	get(t, h, listURL)
	if body := get(t, h, uiURL); string(body) != "UI:um" {
		t.Fatalf("ui %q", body)
	}
	if body := get(t, h, "/rrrrr/unso-1-assetbundle/"+giftID); string(body) != "ORIGINAL" {
		t.Fatalf("gift %q", body)
	}
}

func TestListDuringBuildKeepsLastServed(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	first := start(t, r, translateUI)
	first.wait()
	get(t, first.Wrap(next(r)), listURL)

	r.setPack(t, "dois")
	release := make(chan struct{})
	held := func(raw []byte, name string, values map[string]string) ([]byte, uint32, bool, error) {
		<-release
		return translateUI(raw, name, values)
	}
	second := start(t, r, held)
	h := second.Wrap(next(r))
	revision, entries := listOf(t, get(t, h, listURL))
	if revision != 1817 || entries[uiID].Size != 5 {
		t.Fatalf("during the build: revision %d ui %+v", revision, entries[uiID])
	}
	if body := get(t, h, uiURL); string(body) != "UI:um" {
		t.Fatalf("during the build: ui %q", body)
	}
	close(release)
	second.wait()
	revision, entries = listOf(t, get(t, h, listURL))
	if revision != 1818 || entries[uiID].Size != 7 {
		t.Fatalf("after the build: revision %d ui %+v", revision, entries[uiID])
	}
	if body := get(t, h, uiURL); string(body) != "UI:dois" {
		t.Fatalf("after the build: ui %q", body)
	}
}

func TestBuildFinishingMidSessionServesOnlyWhatTheListNames(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	release := make(chan struct{})
	tr := start(t, r, func(raw []byte, name string, values map[string]string) ([]byte, uint32, bool, error) {
		<-release
		return translateUI(raw, name, values)
	})
	h := tr.Wrap(next(r))
	get(t, h, listURL) // the game now holds the original list
	close(release)
	tr.wait()
	if body := get(t, h, uiURL); string(body) != "ORIGINAL" {
		t.Fatalf("translated bundle sent against the original list: %q", body)
	}
}

func TestFileNamesOnlyTheServedBuild(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	tr := start(t, r, translateUI)
	tr.wait()
	if _, _, ok := tr.File(uiID); ok {
		t.Fatal("a build the game holds no list for was named")
	}
	get(t, tr.Wrap(next(r)), listURL)
	path, sum, ok := tr.File(uiID)
	if !ok || sum != tr.served.Entries[uiID].MD5 {
		t.Fatalf("%s %s %v", path, sum, ok)
	}
	if data, err := os.ReadFile(path); err != nil || string(data) != "UI:um" {
		t.Fatalf("%q %v", data, err)
	}
	if _, _, ok := tr.File(giftID); ok {
		t.Fatal("an untranslated bundle was named")
	}
}

func TestOldBuildRemovedOnceNotServed(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	first := start(t, r, translateUI)
	first.wait()
	get(t, first.Wrap(next(r)), listURL)
	oldDir := filepath.Join(first.buildsDir, first.served.ID)

	r.setPack(t, "dois")
	second := start(t, r, translateUI)
	second.wait()
	if _, err := os.Stat(oldDir); err != nil {
		t.Fatal("the build the game holds was removed before a new list was served")
	}
	get(t, second.Wrap(next(r)), "/v1/list/300116832/1817")
	if _, err := os.Stat(oldDir); !os.IsNotExist(err) {
		t.Fatal("the build no list names any more is still there")
	}
	if _, err := os.Stat(filepath.Join(second.buildsDir, second.served.ID)); err != nil {
		t.Fatal("the served build was removed")
	}
}

func TestPackRemovedGoesBackUp(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	first := start(t, r, translateUI)
	first.wait()
	get(t, first.Wrap(next(r)), listURL)

	r.removePack(t)
	second := start(t, r, translateUI)
	second.wait()
	h := second.Wrap(next(r))
	revision, entries := listOf(t, get(t, h, listURL))
	if revision != 1818 || entries[uiID].Size != 25733 {
		t.Fatalf("revision %d ui %+v", revision, entries[uiID])
	}
	if body := get(t, h, uiURL); string(body) != "ORIGINAL" {
		t.Fatalf("ui %q", body)
	}
}

func TestLostStateServesAboveTheGame(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	first := start(t, r, translateUI)
	first.wait()
	get(t, first.Wrap(next(r)), listURL) // the game now holds 1817

	r.removePack(t)
	if err := os.Remove(filepath.Join(r.data, "translation-state.json")); err != nil {
		t.Fatal(err)
	}
	second := start(t, r, translateUI)
	second.wait()
	revision, entries := listOf(t, get(t, second.Wrap(next(r)), "/v1/list/300116832/1817"))
	if revision != 1818 || entries[uiID].Size != 25733 {
		t.Fatalf("revision %d ui %+v", revision, entries[uiID])
	}
}

func TestRestartSamePackNoRebuild(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	first := start(t, r, translateUI)
	first.wait()
	get(t, first.Wrap(next(r)), listURL)

	second := start(t, r, func([]byte, string, map[string]string) ([]byte, uint32, bool, error) {
		t.Error("rebuilt after a restart with the same pack")
		return nil, 0, false, nil
	})
	second.wait()
	if revision, _ := listOf(t, get(t, second.Wrap(next(r)), listURL)); revision != 1817 {
		t.Fatalf("revision %d", revision)
	}
}

func TestIOSLayout(t *testing.T) {
	r := newRootsIn(t, "ios")
	r.setPack(t, "um")
	tr := startOn(t, r, "ios", translateUI)
	tr.wait()
	h := tr.Wrap(next(r))
	if revision, entries := listOf(t, get(t, h, listURL)); revision != 1817 || entries[uiID].Size != 5 {
		t.Fatalf("revision %d ui %+v", revision, entries[uiID])
	}
	if body := get(t, h, uiURL); string(body) != "UI:um" {
		t.Fatalf("ui %q", body)
	}
}

func TestStartKeepsOnlyEnglishTextEntries(t *testing.T) {
	r := newRoots(t)
	list, _ := sampleList()
	list = append(list, listItem("zz0000", "ui)skill)icon", 10, 1, "00000000000000000000000000000000")...)
	list = append(list, listItem("jj0000", "text)ja)ui", 10, 1, "00000000000000000000000000000000")...)
	if err := os.WriteFile(filepath.Join(r.asset, "assets/revisions/0/list.bin"), list, 0644); err != nil {
		t.Fatal(err)
	}
	r.setPack(t, "um")
	tr := start(t, r, translateUI)
	tr.wait()
	if len(tr.entries) != 2 {
		t.Fatalf("%d entries kept", len(tr.entries))
	}
}

func TestStartUsesListCache(t *testing.T) {
	r := newRoots(t)
	first := start(t, r, translateUI)
	first.wait()
	listPath := filepath.Join(r.asset, "assets/revisions/0/list.bin")
	info, err := os.Stat(listPath)
	if err != nil {
		t.Fatal(err)
	}
	// same size and time, other bytes: a start that read the file would see another md5
	if err := os.WriteFile(listPath, make([]byte, info.Size()), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.Chtimes(listPath, info.ModTime(), info.ModTime()); err != nil {
		t.Fatal(err)
	}
	second := start(t, r, translateUI)
	second.wait()
	if !second.ready || second.listMD5 != first.listMD5 || second.original != 817 || len(second.entries) != 2 {
		t.Fatalf("cache not used: ready %v md5 %s original %d entries %d", second.ready, second.listMD5, second.original, len(second.entries))
	}
}

func TestListCacheFollowsNewGameFiles(t *testing.T) {
	r := newRoots(t)
	first := start(t, r, translateUI)
	first.wait()
	listPath := filepath.Join(r.asset, "assets/revisions/0/list.bin")
	list, _ := sampleList()
	list = append(list, listItem("nn0000", "text)en)new", 10, 1, "00000000000000000000000000000000")...)
	if err := os.WriteFile(listPath, list, 0644); err != nil {
		t.Fatal(err)
	}
	second := start(t, r, translateUI)
	second.wait()
	if second.listMD5 == first.listMD5 || len(second.entries) != 3 {
		t.Fatalf("stale cache: md5 %s entries %d", second.listMD5, len(second.entries))
	}
}

func TestV2ListPath(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	tr := start(t, r, translateUI)
	tr.wait()
	if revision, _ := listOf(t, get(t, tr.Wrap(next(r)), "/v2/pub/a/1/v/2/list/817")); revision != 1817 {
		t.Fatalf("revision %d", revision)
	}
}
