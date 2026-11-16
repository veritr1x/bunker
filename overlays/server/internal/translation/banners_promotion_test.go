package translation

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/mobile/unityasset"
)

func addTemplate(t *testing.T, r roots, path, name string, pixels []byte) {
	t.Helper()
	rev := filepath.Join(r.asset, "assets/revisions/0")
	raw := templateBanner(t, path, name, pixels)
	file := filepath.Join(rev, "assetbundle", strings.ReplaceAll(path, ")", "/")+".assetbundle")
	os.MkdirAll(filepath.Dir(file), 0755)
	if err := os.WriteFile(file, raw, 0644); err != nil {
		t.Fatal(err)
	}
	list, _ := os.ReadFile(filepath.Join(rev, "list.bin"))
	list = append(list, listItem("P"+name+strings.Split(path, ")")[2], path, uint64(len(raw)), 1, "00000000000000000000000000000000")...)
	os.WriteFile(filepath.Join(rev, "list.bin"), list, 0644)
}

// Mama's News images the game files lack in a language are built from another
// language's bundle: the welcome-back pages (prm218, prm219) from Japanese, prm218
// with the image recreate_promotions.py made; global events' pages from English.
func TestMamaNewsImagesJoinTheList(t *testing.T) {
	r := bannerRoots(t)
	ja218, ja219, en9004 := bytes.Repeat([]byte{0x21}, 32), bytes.Repeat([]byte{0x22}, 32), bytes.Repeat([]byte{0x90}, 32)
	addTemplate(t, r, "ui)mom_promotion)ja)banner)prm218", "prm218", ja218)
	addTemplate(t, r, "ui)mom_promotion)ja)banner)prm219", "prm219", ja219)
	addTemplate(t, r, "ui)mom_promotion)en)banner)prm9004", "prm9004", en9004)
	welcome := bytes.Repeat([]byte{0xAB}, 32)
	tr := startBanners(t, r, noticePack(map[string][]byte{"web/bunker/promotion/en/prm218.astc": welcome}))
	h := tr.Wrap(next(r))
	_, entries := listOf(t, get(t, h, listURL))
	byPath := map[string]Entry{}
	for _, e := range entries {
		byPath[e.Path] = e
	}
	for path, want := range map[string][]byte{
		"ui)mom_promotion)en)banner)prm218":  welcome,
		"ui)mom_promotion)en)banner)prm219":  ja219,
		"ui)mom_promotion)ko)banner)prm219":  ja219,
		"ui)mom_promotion)ja)banner)prm9004": en9004,
	} {
		e, ok := byPath[path]
		if !ok {
			t.Fatalf("%s not listed", path)
		}
		b := openBanner(t, get(t, h, "/rrrrr/unso-1-assetbundle/"+e.ObjectID+"?generation=1&alt=media"), path)
		if !bytes.Equal(b.nodes[1].data, want) {
			t.Fatalf("%s: wrong image", path)
		}
		lang := strings.Split(path, ")")[2]
		from := "ja"
		if lang == "ja" {
			from = "en"
		}
		data := b.nodes[0].data
		if !bytes.Contains(data, []byte(")"+lang+")")) || !bytes.Contains(data, []byte("/"+lang+"/")) ||
			bytes.Contains(data, []byte(")"+from+")")) || bytes.Contains(data, []byte("/"+from+"/")) {
			t.Fatalf("%s: the bundle still names %s: %q", path, from, data)
		}
	}
	if _, ok := byPath["ui)mom_promotion)ko)banner)prm218"]; ok {
		t.Fatal("prm218 listed for Korean without its image: it would say Comeback Campaign in Japanese")
	}
	if _, ok := byPath["ui)mom_promotion)ja)banner)prm1072"]; ok {
		t.Fatal("prm1072 listed for Japanese though the game files lack the English one it is built from")
	}
}

// With the game files (ARCHIVE_DUMP) and recreate_promotions.py's output
// (HOME_STRIPS, its --out): each image's bundle opens as the game's do, its
// texture named as the image.
func TestRealMamaNewsImagesOpenInTheGame(t *testing.T) {
	assets := dumpRevision(t)
	out := os.Getenv("HOME_STRIPS")
	if out == "" {
		t.Skip("set HOME_STRIPS to recreate_promotions.py's --out")
	}
	for _, s := range promotionSpecs() {
		raw, err := os.ReadFile(bannerBundlePath(assets, s.Template))
		if err != nil {
			t.Fatal(err)
		}
		var pixels []byte
		if s.NeedsImage {
			if pixels, err = os.ReadFile(filepath.Join(out, strings.TrimPrefix(s.PackImages[0], "web/bunker/"))); err != nil {
				t.Fatal(err)
			}
		}
		bundle, _, err := buildBanner(raw, s, pixels)
		if err != nil {
			t.Fatal(err)
		}
		plain, err := unityasset.Unmask(bundle, s.Path)
		if err != nil {
			t.Fatal(err)
		}
		b, err := unityasset.ParseBundle(plain)
		if err != nil {
			t.Fatal(err)
		}
		textures, err := b.Textures()
		image := s.Path[strings.LastIndex(s.Path, ")")+1:]
		if err != nil || len(textures) != 1 || textures[0].Name != image {
			t.Fatalf("%s: %d textures, %v", s.Path, len(textures), err)
		}
		png, _ := textures[0].PNG()
		file := filepath.Join(os.TempDir(), strings.ReplaceAll(s.Path, ")", "_")+".png")
		os.WriteFile(file, png, 0644)
		t.Logf("%s: %dx%d %s", s.Path, textures[0].Width, textures[0].Height, file)
	}
}
