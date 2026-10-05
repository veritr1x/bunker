package unityasset

import (
	"bytes"
	"errors"
	"fmt"
	"image"
	"image/png"
	"os"
	"path"
	"path/filepath"
	"strings"
)

// Texture is one decoded Texture2D, rows top first.
type Texture struct {
	Name          string
	Width, Height int
	RGBA          []byte
}

// Unity TextureFormat values used by the game's bundles.
const (
	formatAlpha8    = 1
	formatRGB24     = 3
	formatRGBA32    = 4
	formatARGB32    = 5
	formatETC1      = 34
	formatETC2RGB   = 45
	formatETC2RGBA8 = 47
	formatASTC      = 48 // 48–53 RGB 4x4…12x12, 54–59 RGBA 4x4…12x12
)

var astcBlocks = [6]int{4, 5, 6, 8, 10, 12}

func num(v any) int {
	switch x := v.(type) {
	case int64:
		return int(x)
	case float64:
		return int(x)
	}
	return 0
}

// imageData returns a texture's pixels, from the object or its streamed .resS file.
func imageData(b *Bundle, fields map[string]any) ([]byte, error) {
	if data, ok := fields["image data"].([]byte); ok && len(data) > 0 {
		return data, nil
	}
	stream, _ := fields["m_StreamData"].(map[string]any)
	source, _ := stream["path"].(string)
	if source == "" {
		return nil, errors.New("texture has no image data")
	}
	name := path.Base(strings.TrimPrefix(source, "archive:/"))
	file, ok := b.Files[name]
	if !ok {
		return nil, fmt.Errorf("streamed texture data %s is not in this bundle", name)
	}
	offset, size := num(stream["offset"]), num(stream["size"])
	if offset < 0 || size < 0 || offset+size > len(file) {
		return nil, errors.New("streamed texture data lies outside its file")
	}
	return file[offset : offset+size], nil
}

func decodePixels(format, w, h int, data []byte) ([]byte, error) {
	out := make([]byte, w*h*4)
	need := func(n int) error {
		if len(data) < n {
			return fmt.Errorf("texture data is %d bytes, expected %d", len(data), n)
		}
		return nil
	}
	switch {
	case format >= formatASTC && format <= 59:
		bs := astcBlocks[(format-formatASTC)%6]
		return DecodeASTC(data, w, h, bs, bs)
	case format == formatETC1 || format == formatETC2RGB || format == formatETC2RGBA8:
		return DecodeETC(data, w, h, format)
	case format == formatRGBA32:
		if err := need(w * h * 4); err != nil {
			return nil, err
		}
		copy(out, data)
	case format == formatARGB32:
		if err := need(w * h * 4); err != nil {
			return nil, err
		}
		for i := 0; i < w*h; i++ {
			out[i*4], out[i*4+1], out[i*4+2], out[i*4+3] = data[i*4+1], data[i*4+2], data[i*4+3], data[i*4]
		}
	case format == formatRGB24:
		if err := need(w * h * 3); err != nil {
			return nil, err
		}
		for i := 0; i < w*h; i++ {
			out[i*4], out[i*4+1], out[i*4+2], out[i*4+3] = data[i*3], data[i*3+1], data[i*3+2], 255
		}
	case format == formatAlpha8:
		if err := need(w * h); err != nil {
			return nil, err
		}
		for i := 0; i < w*h; i++ {
			out[i*4], out[i*4+1], out[i*4+2], out[i*4+3] = 255, 255, 255, data[i]
		}
	default:
		return nil, fmt.Errorf("texture format %d is not supported", format)
	}
	return out, nil
}

// Textures decodes every Texture2D in a bundle.
func (b *Bundle) Textures() ([]Texture, error) {
	var out []Texture
	for name, file := range b.Files {
		if strings.HasSuffix(name, ".resS") || strings.HasSuffix(name, ".resource") {
			continue
		}
		sf, err := ParseSerializedFile(file)
		if err != nil {
			continue // not a serialized file
		}
		objects, err := sf.Objects(classIDs["Texture2D"])
		if err != nil {
			return nil, err
		}
		for _, o := range objects {
			w, h := num(o.Fields["m_Width"]), num(o.Fields["m_Height"])
			if w <= 0 || h <= 0 || w > 8192 || h > 8192 {
				continue
			}
			data, err := imageData(b, o.Fields)
			if err != nil {
				return nil, err
			}
			pixels, err := decodePixels(num(o.Fields["m_TextureFormat"]), w, h, data)
			if err != nil {
				return nil, err
			}
			// Unity stores the bottom row first.
			row := w * 4
			flipped := make([]byte, len(pixels))
			for y := 0; y < h; y++ {
				copy(flipped[y*row:(y+1)*row], pixels[(h-1-y)*row:(h-y)*row])
			}
			name, _ := o.Fields["m_Name"].(string)
			out = append(out, Texture{Name: name, Width: w, Height: h, RGBA: flipped})
		}
	}
	return out, nil
}

// PNG encodes the texture.
func (t Texture) PNG() ([]byte, error) {
	img := &image.NRGBA{Pix: t.RGBA, Stride: t.Width * 4, Rect: image.Rect(0, 0, t.Width, t.Height)}
	var buf bytes.Buffer
	if err := (&png.Encoder{CompressionLevel: png.BestSpeed}).Encode(&buf, img); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// Trim drops fully transparent rows and columns around the picture, keeping a small margin.
func (t Texture) Trim() Texture {
	top, bottom, left, right := t.Height, -1, t.Width, -1
	for y := 0; y < t.Height; y++ {
		for x := 0; x < t.Width; x++ {
			if t.RGBA[(y*t.Width+x)*4+3] != 0 {
				top, bottom = min(top, y), max(bottom, y)
				left, right = min(left, x), max(right, x)
			}
		}
	}
	if bottom < 0 {
		return t
	}
	pad := max(t.Width, t.Height) / 64
	top, left = max(0, top-pad), max(0, left-pad)
	bottom, right = min(t.Height-1, bottom+pad), min(t.Width-1, right+pad)
	w, h := right-left+1, bottom-top+1
	if w == t.Width && h == t.Height {
		return t
	}
	out := make([]byte, w*h*4)
	for y := 0; y < h; y++ {
		copy(out[y*w*4:(y+1)*w*4], t.RGBA[((top+y)*t.Width+left)*4:((top+y)*t.Width+left+w)*4])
	}
	return Texture{Name: t.Name, Width: w, Height: h, RGBA: out}
}

// Shrink scales the texture down by box filtering so neither side exceeds maxSide.
func (t Texture) Shrink(maxSide int) Texture {
	if maxSide <= 0 || (t.Width <= maxSide && t.Height <= maxSide) {
		return t
	}
	scale := float64(maxSide) / float64(max(t.Width, t.Height))
	w, h := max(1, int(float64(t.Width)*scale+0.5)), max(1, int(float64(t.Height)*scale+0.5))
	out := make([]byte, w*h*4)
	for y := 0; y < h; y++ {
		y0, y1 := y*t.Height/h, max(y*t.Height/h+1, (y+1)*t.Height/h)
		for x := 0; x < w; x++ {
			x0, x1 := x*t.Width/w, max(x*t.Width/w+1, (x+1)*t.Width/w)
			var sum [4]int
			for sy := y0; sy < y1; sy++ {
				for sx := x0; sx < x1; sx++ {
					p := (sy*t.Width + sx) * 4
					for c := 0; c < 4; c++ {
						sum[c] += int(t.RGBA[p+c])
					}
				}
			}
			n := (y1 - y0) * (x1 - x0)
			for c := 0; c < 4; c++ {
				out[(y*w+x)*4+c] = byte(sum[c] / n)
			}
		}
	}
	return Texture{Name: t.Name, Width: w, Height: h, RGBA: out}
}

// TextureToPNG writes the bundle's largest texture to target as a PNG, through a temporary
// file; maxSide > 0 trims transparent margins and shrinks it to fit.
func TextureToPNG(bundlePath, target string, maxSide int) error {
	b, err := OpenBundle(bundlePath)
	if err != nil {
		return err
	}
	textures, err := b.Textures()
	if err != nil {
		return err
	}
	if len(textures) == 0 {
		return errors.New("no texture in this bundle")
	}
	best := textures[0]
	for _, t := range textures[1:] {
		if t.Width*t.Height > best.Width*best.Height {
			best = t
		}
	}
	if maxSide > 0 {
		best = best.Trim().Shrink(maxSide)
	}
	data, err := best.PNG()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return err
	}
	pending := target + ".tmp"
	if err := os.WriteFile(pending, data, 0o644); err != nil {
		return err
	}
	return os.Rename(pending, target)
}
