package unityasset

import (
	"encoding/binary"
	"encoding/json"
	"errors"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// Mecanim clips (Unity 2019) as three.js AnimationClip JSON, with tracks named by bone.
//
// A clip's curves come in three parts, numbered in this order: streamed (cubic
// Hermite keys), dense (evenly spaced samples) and constant values. Each generic
// binding takes the next 3 curves (position, scale, Euler) or 4 (rotation) and names
// its bone by the CRC32 of its path, which the costume's Avatar (m_TOS) maps back to a
// path. Mirrored into glTF space like the model: X for positions, Y and Z for rotations.

type streamedKey struct {
	time  float32
	coeff [4]float32
}

type curve struct {
	keys     []streamedKey // streamed
	samples  []float32     // dense
	constant float32
	kind     int // 0 streamed, 1 dense, 2 constant
}

func (c *curve) at(t float32, denseBegin, denseRate float32) float32 {
	switch c.kind {
	case 1:
		if len(c.samples) == 0 {
			return 0
		}
		f := (t - denseBegin) * denseRate
		i := int(math.Floor(float64(f)))
		if i < 0 {
			return c.samples[0]
		}
		if i >= len(c.samples)-1 {
			return c.samples[len(c.samples)-1]
		}
		frac := f - float32(i)
		return c.samples[i]*(1-frac) + c.samples[i+1]*frac
	case 2:
		return c.constant
	}
	// The last key at or before t holds the cubic for this stretch of time.
	i := sort.Search(len(c.keys), func(i int) bool { return c.keys[i].time > t }) - 1
	if i < 0 {
		if len(c.keys) == 0 {
			return 0
		}
		i = 0
	}
	k := c.keys[i]
	dt := t - k.time
	return ((k.coeff[0]*dt+k.coeff[1])*dt+k.coeff[2])*dt + k.coeff[3]
}

func floatList(v any) []float32 {
	items, _ := v.([]any)
	out := make([]float32, len(items))
	for i, x := range items {
		f, _ := x.(float64)
		out[i] = float32(f)
	}
	return out
}

func readCurves(clip map[string]any) ([]curve, float32, float32, error) {
	muscle, _ := clip["m_MuscleClip"].(map[string]any)
	inner, _ := muscle["m_Clip"].(map[string]any)
	data, _ := inner["data"].(map[string]any)
	streamed, _ := data["m_StreamedClip"].(map[string]any)
	dense, _ := data["m_DenseClip"].(map[string]any)
	constant, _ := data["m_ConstantClip"].(map[string]any)

	var curves []curve
	// Streamed: frames of {time, count, count × {index, 4 coefficients}} packed in uint32s.
	words, _ := streamed["data"].([]any)
	raw := make([]byte, len(words)*4)
	for i, w := range words {
		binary.LittleEndian.PutUint32(raw[i*4:], uint32(num(w)))
	}
	streamedCount := num(streamed["curveCount"])
	sc := make([]curve, streamedCount)
	for p := 0; p+8 <= len(raw); {
		t := math.Float32frombits(binary.LittleEndian.Uint32(raw[p:]))
		n := int(binary.LittleEndian.Uint32(raw[p+4:]))
		p += 8
		for k := 0; k < n; k++ {
			if p+20 > len(raw) {
				return nil, 0, 0, errors.New("streamed clip is cut short")
			}
			idx := int(binary.LittleEndian.Uint32(raw[p:]))
			var key streamedKey
			key.time = t
			for c := 0; c < 4; c++ {
				key.coeff[c] = math.Float32frombits(binary.LittleEndian.Uint32(raw[p+4+c*4:]))
			}
			p += 20
			// The first and last frames are sentinels at -Inf and +Inf.
			finite := !math.IsInf(float64(t), 0) && !math.IsNaN(float64(t))
			if finite && idx >= 0 && idx < streamedCount {
				sc[idx].keys = append(sc[idx].keys, key)
			}
		}
	}
	curves = append(curves, sc...)
	// Dense: frame-major samples.
	denseCurves := num(dense["m_CurveCount"])
	frames := num(dense["m_FrameCount"])
	samples := floatList(dense["m_SampleArray"])
	for c := 0; c < denseCurves; c++ {
		cv := curve{kind: 1}
		for f := 0; f < frames && f*denseCurves+c < len(samples); f++ {
			cv.samples = append(cv.samples, samples[f*denseCurves+c])
		}
		curves = append(curves, cv)
	}
	for _, v := range floatList(constant["data"]) {
		curves = append(curves, curve{kind: 2, constant: v})
	}
	rate := float32(0)
	if r, ok := dense["m_SampleRate"].(float64); ok {
		rate = float32(r)
	}
	begin := float32(0)
	if b, ok := dense["m_BeginTime"].(float64); ok {
		begin = float32(b)
	}
	return curves, begin, rate, nil
}

// Track is one three.js KeyframeTrack.
type Track struct {
	Name   string    `json:"name"`
	Type   string    `json:"type"`
	Times  []float32 `json:"times"`
	Values []float32 `json:"values"`
}

// Clip is a three.js AnimationClip in its JSON form.
type Clip struct {
	Name     string  `json:"name"`
	Duration float32 `json:"duration"`
	Tracks   []Track `json:"tracks"`
}

// avatarPaths maps path CRC32s to the full bone path, from a skeleton bundle's Avatar.
func avatarPaths(a *assets, skeleton *loadedFile) (map[uint32]string, error) {
	avatars, err := skeleton.sf.Objects(classIDs["Avatar"])
	if err != nil || len(avatars) == 0 {
		return nil, errors.New("the costume has no avatar")
	}
	tos, _ := avatars[0].Fields["m_TOS"].([]any)
	out := map[uint32]string{}
	for _, e := range tos {
		pair, _ := e.(map[string]any)
		p, _ := pair["second"].(string)
		out[uint32(num(pair["first"]))] = p
	}
	return out, nil
}

// ClipToJSON converts the clip in clipBundle for the costume in actorFolder, sampled at fps.
func ClipToJSON(clipBundle, actorFolder, target string, fps float32) error {
	a := &assets{byCAB: map[string]*loadedFile{}}
	asset := filepath.Base(actorFolder)
	skeletonPath := filepath.Join(actorFolder, "mesh", "sk_"+asset+".assetbundle")
	if err := a.add(skeletonPath); err != nil {
		return err
	}
	if err := a.add(clipBundle); err != nil {
		return err
	}
	names, err := avatarPaths(a, a.byCABOfBundle(skeletonPath))
	if err != nil {
		return err
	}
	file := a.byCABOfBundle(clipBundle)
	if file == nil {
		return errors.New("not an animation bundle")
	}
	clips, err := file.sf.Objects(classIDs["AnimationClip"])
	if err != nil || len(clips) == 0 {
		return errors.New("no animation clip in this bundle")
	}
	clip := clips[0].Fields
	curves, denseBegin, denseRate, err := readCurves(clip)
	if err != nil {
		return err
	}
	muscle, _ := clip["m_MuscleClip"].(map[string]any)
	start, _ := muscle["m_StartTime"].(float64)
	stop, _ := muscle["m_StopTime"].(float64)
	duration := float32(stop - start)
	if duration <= 0 {
		duration = 1 / fps
	}
	frames := int(math.Ceil(float64(duration*fps))) + 1
	times := make([]float32, frames)
	for i := range times {
		times[i] = min(float32(i)/fps, duration)
	}
	bindingsHolder, _ := clip["m_ClipBindingConstant"].(map[string]any)
	bindings, _ := bindingsHolder["genericBindings"].([]any)
	out := Clip{Name: strings.TrimSuffix(filepath.Base(clipBundle), ".assetbundle"), Duration: duration}
	next := 0
	for _, b := range bindings {
		bm, _ := b.(map[string]any)
		typeID, attribute := num(bm["typeID"]), num(bm["attribute"])
		width := 1
		if typeID == 4 {
			switch attribute {
			case 1, 3, 4:
				width = 3
			case 2:
				width = 4
			}
		}
		first := next
		next += width
		if typeID != 4 || next > len(curves) {
			continue // Animator root motion, blend shapes and other properties are not shown
		}
		bonePath, ok := names[uint32(num(bm["path"]))]
		if !ok || bonePath == "" {
			continue
		}
		bone := bonePath[strings.LastIndex(bonePath, "/")+1:]
		// The top bone carries root motion; keep it on the spot so the viewer's camera stays on the character.
		inPlace := attribute == 1 && !strings.Contains(bonePath, "/")
		track := Track{Name: bone, Times: times}
		for _, t := range times {
			v := make([]float32, width)
			for c := 0; c < width; c++ {
				v[c] = curves[first+c].at(float32(start)+t, denseBegin, denseRate)
			}
			switch attribute {
			case 1: // position
				if inPlace && len(track.Values) >= 3 {
					v[0], v[2] = -track.Values[0], track.Values[2]
				}
				track.Values = append(track.Values, -v[0], v[1], v[2])
			case 2: // rotation
				l := float32(math.Sqrt(float64(v[0]*v[0] + v[1]*v[1] + v[2]*v[2] + v[3]*v[3])))
				if l == 0 {
					l = 1
				}
				track.Values = append(track.Values, v[0]/l, -v[1]/l, -v[2]/l, v[3]/l)
			case 3: // scale
				track.Values = append(track.Values, v...)
			case 4: // Euler degrees, Unity's Z-X-Y order, as a quaternion
				q := eulerToQuaternion(v[0], v[1], v[2])
				track.Values = append(track.Values, q[0], -q[1], -q[2], q[3])
			}
		}
		switch attribute {
		case 1:
			track.Name, track.Type = bone+".position", "vector"
		case 2, 4:
			track.Name, track.Type = bone+".quaternion", "quaternion"
		case 3:
			track.Name, track.Type = bone+".scale", "vector"
		}
		out.Tracks = append(out.Tracks, track)
	}
	if len(out.Tracks) == 0 {
		return errors.New("this clip moves no bones of this costume")
	}
	data, err := json.Marshal(out)
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

func eulerToQuaternion(x, y, z float32) [4]float32 {
	rad := float64(math.Pi / 360) // half angle, degrees to radians
	cx, sx := math.Cos(float64(x)*rad), math.Sin(float64(x)*rad)
	cy, sy := math.Cos(float64(y)*rad), math.Sin(float64(y)*rad)
	cz, sz := math.Cos(float64(z)*rad), math.Sin(float64(z)*rad)
	// q = qy * qx * qz (Unity applies Z, then X, then Y)
	return [4]float32{
		float32(cy*sx*cz + sy*cx*sz),
		float32(sy*cx*cz - cy*sx*sz),
		float32(cy*cx*sz - sy*sx*cz),
		float32(cy*cx*cz + sy*sx*sz),
	}
}
