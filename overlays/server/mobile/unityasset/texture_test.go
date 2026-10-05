package unityasset

import (
	"image"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestMaskName(t *testing.T) {
	got := MaskName("/x/revisions/0/assetbundle/ui/still/season1/still_main_1101401.assetbundle")
	if got != "ui)still)season1)still_main_1101401" {
		t.Fatal(got)
	}
}

func TestUnmaskCoversTheFirst256Bytes(t *testing.T) {
	plain := make([]byte, 300)
	copy(plain, "UnityFS")
	for i := 7; i < len(plain); i++ {
		plain[i] = byte(i)
	}
	mask := maskBytes("a)b")
	masked := append([]byte(nil), plain...)
	masked[0] = 0x31
	for i := 1; i < 256; i++ {
		masked[i] ^= mask[i%len(mask)]
	}
	got, err := Unmask(masked, "a)b")
	if err != nil || string(got) != string(plain) {
		t.Fatalf("unmask differs: %v", err)
	}
}

func TestVoidExtentBlockIsOneColour(t *testing.T) {
	block := []byte{0xfc, 0xfd, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0, 10, 0, 20, 0, 30, 0, 40}
	img, err := DecodeASTC(block, 4, 4, 4, 4)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 16; i++ {
		if img[i*4] != 10 || img[i*4+1] != 20 || img[i*4+2] != 30 || img[i*4+3] != 40 {
			t.Fatalf("texel %d is %v", i, img[i*4:i*4+4])
		}
	}
}

// TestTexturesMatchTheReference decodes real bundles and compares every pixel with
// texture2ddecoder's output. Set ARCHIVE_DUMP to revisions/0 and ARCHIVE_TEXTURE_REFS
// to the folder of reference PNGs named like ui__still__season1__still_main_1101401.png.
func TestTexturesMatchTheReference(t *testing.T) {
	dump, refs := os.Getenv("ARCHIVE_DUMP"), os.Getenv("ARCHIVE_TEXTURE_REFS")
	if dump == "" || refs == "" {
		t.Skip("set ARCHIVE_DUMP and ARCHIVE_TEXTURE_REFS")
	}
	files, _ := filepath.Glob(filepath.Join(refs, "*.png"))
	if len(files) == 0 {
		t.Fatal("no reference PNGs")
	}
	for _, ref := range files {
		name := strings.TrimSuffix(filepath.Base(ref), ".png")
		bundle := filepath.Join(dump, "assetbundle", strings.ReplaceAll(name, "__", "/")+".assetbundle")
		t.Run(name, func(t *testing.T) {
			out := filepath.Join(t.TempDir(), "out.png")
			if err := TextureToPNG(bundle, out, 0); err != nil {
				t.Fatal(err)
			}
			got, want := readPNG(t, out), readPNG(t, ref)
			if got.Bounds() != want.Bounds() {
				t.Fatalf("size %v, want %v", got.Bounds(), want.Bounds())
			}
			diff := 0
			for i := range got.Pix {
				if got.Pix[i] != want.Pix[i] {
					diff++
				}
			}
			if diff > 0 {
				t.Fatalf("%d of %d channel values differ", diff, len(got.Pix))
			}
		})
	}
}

func TestShrinkKeepsTheAspect(t *testing.T) {
	tex := Texture{Width: 400, Height: 200, RGBA: make([]byte, 400*200*4)}
	for i := range tex.RGBA {
		tex.RGBA[i] = 200
	}
	small := tex.Shrink(100)
	if small.Width != 100 || small.Height != 50 || small.RGBA[0] != 200 {
		t.Fatalf("%dx%d %d", small.Width, small.Height, small.RGBA[0])
	}
}

func TestTrimKeepsThePicture(t *testing.T) {
	tex := Texture{Width: 128, Height: 128, RGBA: make([]byte, 128*128*4)}
	tex.RGBA[(64*128+40)*4+3] = 255 // one opaque texel
	got := tex.Trim()
	if got.Width != 5 || got.Height != 5 || got.RGBA[(2*5+2)*4+3] != 255 {
		t.Fatalf("%dx%d", got.Width, got.Height)
	}
}

func readPNG(t *testing.T, path string) *image.NRGBA {
	f, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	img, err := png.Decode(f)
	if err != nil {
		t.Fatal(err)
	}
	b := img.Bounds()
	out := image.NewNRGBA(b)
	for y := b.Min.Y; y < b.Max.Y; y++ {
		for x := b.Min.X; x < b.Max.X; x++ {
			out.Set(x, y, img.At(x, y))
		}
	}
	return out
}
