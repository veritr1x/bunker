package translation

import (
	"bytes"
	"errors"
	"hash/crc32"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"lunar-tear/server/mobile/unityasset"
)

const templateCAB = "CAB-6e5721078876bd9aacd3392bfa7d7ec6"

// templateBanner is a masked two-file bundle shaped like the game's banners:
// a serialized file naming the banner and its .resS, then the pixels.
func templateBanner(t *testing.T, path, name string, pixels []byte) []byte {
	t.Helper()
	serialized := []byte("head " + templateCAB + " archive:/" + templateCAB + "/" + templateCAB + ".resS " +
		strings.ReplaceAll(path, ")", "/") + " " + path + " " + name + " " + name + ".png tail")
	plain, err := writeNodes(&nodeBundle{version: 6, unityVersion: "5.x.x", unityRevision: "2019.4.9f1", flags: 0x43, hash: make([]byte, 16),
		nodes: []node{{flags: 4, name: templateCAB, data: serialized}, {flags: 0, name: templateCAB + ".resS", data: pixels}}})
	if err != nil {
		t.Fatal(err)
	}
	return Mask(plain, path, 0x32)
}

func openBanner(t *testing.T, raw []byte, path string) *nodeBundle {
	t.Helper()
	plain, err := unityasset.Unmask(raw, path)
	if err != nil {
		t.Fatal(err)
	}
	b, err := readNodes(plain)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func TestBuildBannerRenamesAndSwapsPixels(t *testing.T) {
	template := "ui)quest)en)banner)event_banner_512"
	raw := templateBanner(t, template, "event_banner_512", bytes.Repeat([]byte{1}, 32))
	spec := bannerSpec{Path: "ui)quest)en)banner)event_banner_900", Template: template, Old: "event_banner_512", New: "event_banner_900"}
	pixels := bytes.Repeat([]byte{9}, 32)
	out, crc, err := buildBanner(raw, spec, pixels)
	if err != nil {
		t.Fatal(err)
	}
	b := openBanner(t, out, spec.Path)
	if len(b.nodes) != 2 {
		t.Fatalf("%d files", len(b.nodes))
	}
	serialized, resS := b.nodes[0].data, b.nodes[1].data
	for _, gone := range []string{"512", templateCAB} {
		if bytes.Contains(serialized, []byte(gone)) || strings.Contains(b.nodes[0].name, gone) {
			t.Fatalf("%q left in the bundle", gone)
		}
	}
	cab := b.nodes[0].name
	if len(cab) != len(templateCAB) || b.nodes[1].name != cab+".resS" || !bytes.Contains(serialized, []byte("archive:/"+cab+"/"+cab+".resS")) {
		t.Fatalf("file names %q, %q", cab, b.nodes[1].name)
	}
	for _, want := range []string{"ui/quest/en/banner/event_banner_900", spec.Path, "event_banner_900.png"} {
		if !bytes.Contains(serialized, []byte(want)) {
			t.Fatalf("%q missing", want)
		}
	}
	if !bytes.Equal(resS, pixels) {
		t.Fatal("pixels not swapped")
	}
	if want := crc32.ChecksumIEEE(append(append([]byte{}, serialized...), resS...)); crc != want {
		t.Fatalf("crc %d, want %d (both files, as list.bin keeps it)", crc, want)
	}
}

func TestBuildBannerKeepsPixelsWithoutNew(t *testing.T) {
	template := "ui)quest)ja)banner)event_banner_512"
	raw := templateBanner(t, template, "event_banner_512", bytes.Repeat([]byte{1}, 32))
	spec := bannerSpec{Path: "ui)quest)ja)banner)event_banner_900", Template: template, Old: "event_banner_512", New: "event_banner_900"}
	out, _, err := buildBanner(raw, spec, nil)
	if err != nil {
		t.Fatal(err)
	}
	if b := openBanner(t, out, spec.Path); !bytes.Equal(b.nodes[1].data, bytes.Repeat([]byte{1}, 32)) {
		t.Fatal("pixels changed")
	}
}

func TestBuildBannerRefuses(t *testing.T) {
	template := "ui)quest)en)banner)event_banner_512"
	raw := templateBanner(t, template, "event_banner_512", bytes.Repeat([]byte{1}, 32))
	good := bannerSpec{Path: "ui)quest)en)banner)event_banner_900", Template: template, Old: "event_banner_512", New: "event_banner_900"}
	for name, c := range map[string]struct {
		spec   bannerSpec
		pixels []byte
	}{
		"pixels of another size":  {good, make([]byte, 31)},
		"names of another length": {bannerSpec{Path: "ui)quest)en)banner)event_banner_9000", Template: template, Old: "event_banner_512", New: "event_banner_9000"}, nil},
		"a name the bundle lacks": {bannerSpec{Path: good.Path, Template: template, Old: "event_banner_513", New: "event_banner_900"}, nil},
	} {
		if _, _, err := buildBanner(raw, c.spec, c.pixels); err == nil {
			t.Errorf("%s: built", name)
		}
	}
	if _, _, err := buildBanner([]byte("not a bundle"), good, nil); err == nil {
		t.Error("damaged bundle: built")
	}
}

func TestPatchListAddsEntries(t *testing.T) {
	data, _ := sampleList()
	added := newEntry(listItemBody("vqZsA7", "text)en)ui", 25733, 3069911305, "dc1c7484dae87ae3095f9a70c6c3d63b"),
		Entry{ObjectID: "Bnr900", Path: "ui)quest)en)banner)event_banner_900", Size: 50, CRC: 6, MD5: "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd"}, 99)
	out, err := PatchList(data, 818, nil, [][]byte{added})
	if err != nil {
		t.Fatal(err)
	}
	revision, entries, err := ParseList(out)
	if err != nil || revision != 818 || len(entries) != 3 {
		t.Fatalf("revision %d, %d entries, %v", revision, len(entries), err)
	}
	if e := entries[2]; e != (Entry{ObjectID: "Bnr900", Path: "ui)quest)en)banner)event_banner_900", Size: 50, CRC: 6, MD5: "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd"}) {
		t.Fatalf("added %+v", e)
	}
	if !bytes.Contains(out, listItemBody("vqZsA7", "text)en)ui", 25733, 3069911305, "dc1c7484dae87ae3095f9a70c6c3d63b")) {
		t.Fatal("the template entry changed")
	}
}

// bannerRoots is newRoots with the six template banners (three languages, two
// kinds), the home-screen strips and a list naming them.
func bannerRoots(t *testing.T) roots {
	r := newRoots(t)
	rev := filepath.Join(r.asset, "assets/revisions/0")
	list, _ := sampleList()
	n := 0
	for _, lang := range []string{"en", "ja", "ko"} {
		for _, b := range []struct{ path, name string }{
			{"ui)quest)" + lang + ")banner)event_banner_512", "event_banner_512"},
			{"ui)quest)" + lang + ")mom_banner)event_mom_banner_512", "event_mom_banner_512"},
			{"ui)mom_banner)" + lang + ")mom_banner_event_mom_banner_512", "mom_banner_event_mom_banner_512"},
		} {
			pixels := bytes.Repeat([]byte{byte(n)}, 32)
			if strings.HasPrefix(b.path, "ui)mom_banner)") {
				pixels = bytes.Repeat([]byte{0x77}, 32) // the 2021 strip
			}
			raw := templateBanner(t, b.path, b.name, pixels)
			file := filepath.Join(rev, "assetbundle", strings.ReplaceAll(b.path, ")", "/")+".assetbundle")
			os.MkdirAll(filepath.Dir(file), 0755)
			if err := os.WriteFile(file, raw, 0644); err != nil {
				t.Fatal(err)
			}
			list = append(list, listItem("T"+strings.Repeat("x", n%5)+string(rune('a'+n)), b.path, uint64(len(raw)), 1, "00000000000000000000000000000000")...)
			n++
		}
	}
	if err := os.WriteFile(filepath.Join(rev, "list.bin"), list, 0644); err != nil {
		t.Fatal(err)
	}
	return r
}

func noticePack(files map[string][]byte) func(string) ([]byte, error) {
	return func(name string) ([]byte, error) {
		if b, ok := files[name]; ok {
			return b, nil
		}
		return nil, os.ErrNotExist
	}
}

func startBanners(t *testing.T, r roots, pack func(string) ([]byte, error)) *Translator {
	tr := New(r.asset, r.data, "android")
	tr.rebuild = translateUI
	tr.UseNoticePack(pack)
	tr.Start()
	tr.wait()
	return tr
}

func TestBannersJoinTheList(t *testing.T) {
	r := bannerRoots(t)
	recreated := bytes.Repeat([]byte{0xEE}, 32)
	tr := startBanners(t, r, noticePack(map[string][]byte{"web/bunker/banners/en/event_banner_900.astc": recreated}))
	h := tr.Wrap(next(r))
	revision, entries := listOf(t, get(t, h, listURL))
	if revision <= 817 {
		t.Fatalf("revision %d: the game would keep its stored list", revision)
	}
	byPath := map[string]Entry{}
	for _, e := range entries {
		byPath[e.Path] = e
	}
	for _, lang := range []string{"en", "ja", "ko"} {
		for _, path := range []string{"ui)quest)" + lang + ")banner)event_banner_900", "ui)quest)" + lang + ")mom_banner)event_mom_banner_900"} {
			e, ok := byPath[path]
			if !ok {
				t.Fatalf("%s not listed", path)
			}
			body := get(t, h, "/rrrrr/unso-1-assetbundle/"+e.ObjectID+"?generation=1&alt=media")
			if uint64(len(body)) != e.Size {
				t.Fatalf("%s: %d bytes, list says %d", path, len(body), e.Size)
			}
			b := openBanner(t, body, path)
			pixels := b.nodes[1].data
			switch {
			case path == "ui)quest)en)banner)event_banner_900" && !bytes.Equal(pixels, recreated):
				t.Fatalf("%s: not the recreated image", path)
			case strings.Contains(path, "mom_banner") && !bytes.Equal(pixels, bytes.Repeat([]byte{0x77}, 32)):
				t.Fatalf("%s: not the 2021 strip", path)
			}
			if file, _, ok := tr.File(e.ObjectID); !ok || file == "" {
				t.Fatalf("%s: not linked for the game's cache", path)
			}
		}
	}
	if body := get(t, h, uiURL); string(body) != "ORIGINAL" {
		t.Fatal("other assets are no longer the originals")
	}
}

func TestBannersStayAcrossRestarts(t *testing.T) {
	r := bannerRoots(t)
	pack := noticePack(map[string][]byte{"banners/en/event_banner_900.astc": bytes.Repeat([]byte{0xEE}, 32)})
	first, _ := listOf(t, get(t, startBanners(t, r, pack).Wrap(next(r)), listURL))
	again, entries := listOf(t, get(t, startBanners(t, r, pack).Wrap(next(r)), "/v1/list/300116832/"+itoa(first)))
	if again != first || len(entries) != 2+9+6 {
		t.Fatalf("revision %d then %d, %d entries", first, again, len(entries))
	}
}

func TestWithoutTemplatesNoBanners(t *testing.T) {
	r := newRoots(t)
	tr := startBanners(t, r, noticePack(nil))
	original, _ := sampleList()
	if body := get(t, tr.Wrap(next(r)), listURL); !bytes.Equal(body, original) {
		t.Fatal("list changed though nothing was built")
	}
}

func TestBannerPackErrorKeepsTemplatePixels(t *testing.T) {
	r := bannerRoots(t)
	tr := startBanners(t, r, func(string) ([]byte, error) { return nil, errors.New("pack unreadable") })
	_, entries := listOf(t, get(t, tr.Wrap(next(r)), listURL))
	found := false
	for _, e := range entries {
		if e.Path == "ui)quest)en)banner)event_banner_900" {
			found = true
		}
	}
	if !found {
		t.Fatal("banner 900 missing: the calendar would show no banner")
	}
}

func itoa(n uint64) string { return strconv.FormatUint(n, 10) }

// listItemBody is listItem's entry without its list field.
func listItemBody(id, path string, size, crc uint64, md5 string) []byte {
	var e []byte
	e = append(e, protoVarint(1, 7)...)
	e = append(e, protoBytes(3, []byte(path))...)
	e = append(e, protoVarint(4, size)...)
	e = append(e, protoVarint(5, crc)...)
	e = append(e, protoVarint(9, 2)...)
	e = append(e, protoBytes(10, []byte(md5))...)
	e = append(e, protoBytes(11, []byte(id))...)
	e = append(e, protoVarint(12, 1626410850428981)...)
	return e
}

// With the game files (ARCHIVE_DUMP, an extracted revisions/0) and the
// recreated image (BANNER_IMAGE, scripts/recreate_banners.py's en .astc).
func TestRealBannersOpenInTheGame(t *testing.T) {
	assets := dumpRevision(t)
	image, err := os.ReadFile(os.Getenv("BANNER_IMAGE"))
	if err != nil {
		t.Skip("set BANNER_IMAGE to banners/en/event_banner_900.astc")
	}
	for _, s := range bannerSpecs()[:2] { // English
		raw, err := os.ReadFile(bannerBundlePath(assets, s.Template))
		if err != nil {
			t.Fatal(err)
		}
		pixels := image
		if s.FromBundle != "" {
			if pixels, err = bannerPixels(assets, s.FromBundle); err != nil {
				t.Fatal(err)
			}
		}
		out, _, err := buildBanner(raw, s, pixels)
		if err != nil {
			t.Fatal(err)
		}
		plain, err := unityasset.Unmask(out, s.Path)
		if err != nil {
			t.Fatal(err)
		}
		b, err := unityasset.ParseBundle(plain)
		if err != nil {
			t.Fatal(err)
		}
		textures, err := b.Textures()
		if err != nil || len(textures) != 1 {
			t.Fatalf("%s: %d textures, %v", s.Path, len(textures), err)
		}
		tex := textures[0]
		name := s.New
		if tex.Name != name {
			t.Fatalf("%s: texture %q", s.Path, tex.Name)
		}
		png, _ := tex.PNG()
		os.WriteFile(filepath.Join(os.TempDir(), name+".png"), png, 0644)
		t.Logf("%s: %dx%d, %s", s.Path, tex.Width, tex.Height, filepath.Join(os.TempDir(), name+".png"))
	}
}

// Notice pack 6 kept the image at banners/ (launchers' pack check refused it); it is still read.
func TestBannerImageFromNoticePack6(t *testing.T) {
	r := bannerRoots(t)
	recreated := bytes.Repeat([]byte{0xEE}, 32)
	tr := startBanners(t, r, noticePack(map[string][]byte{"banners/en/event_banner_900.astc": recreated}))
	h := tr.Wrap(next(r))
	_, entries := listOf(t, get(t, h, listURL))
	for _, e := range entries {
		if e.Path == "ui)quest)en)banner)event_banner_900" {
			body := get(t, h, "/rrrrr/unso-1-assetbundle/"+e.ObjectID+"?generation=1&alt=media")
			if !bytes.Equal(openBanner(t, body, e.Path).nodes[1].data, recreated) {
				t.Fatal("not the recreated image")
			}
			return
		}
	}
	t.Fatal("banner 900 not listed")
}
