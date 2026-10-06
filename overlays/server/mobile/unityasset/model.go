package unityasset

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strings"
)

// A costume as glTF: the skeleton, every enabled skinned mesh with its bone weights,
// and each material's colour texture. Unity is left-handed; glTF is right-handed, so
// X is mirrored throughout and triangle winding is reversed.

type loadedFile struct {
	bundle *Bundle
	sf     *SerializedFile
	path   string
}

// assets opens bundles and resolves PPtrs between them by their CAB file names.
type assets struct {
	byCAB map[string]*loadedFile
}

func openAssets(folders ...string) (*assets, error) {
	a := &assets{byCAB: map[string]*loadedFile{}}
	for _, folder := range folders {
		files, _ := filepath.Glob(filepath.Join(folder, "*", "*.assetbundle"))
		more, _ := filepath.Glob(filepath.Join(folder, "*.assetbundle"))
		for _, f := range append(files, more...) {
			if err := a.add(f); err != nil {
				return nil, fmt.Errorf("%s: %w", filepath.Base(f), err)
			}
		}
	}
	return a, nil
}

func (a *assets) add(bundlePath string) error {
	b, err := OpenBundle(bundlePath)
	if err != nil {
		return err
	}
	for name, data := range b.Files {
		if strings.HasSuffix(name, ".resS") || strings.HasSuffix(name, ".resource") {
			continue
		}
		sf, err := ParseSerializedFile(data)
		if err != nil {
			continue
		}
		a.byCAB[name] = &loadedFile{bundle: b, sf: sf, path: bundlePath}
	}
	return nil
}

func pptr(v any) (fileID int, pathID int64) {
	m, _ := v.(map[string]any)
	f, _ := m["m_FileID"].(int64)
	p, _ := m["m_PathID"].(int64)
	return int(f), p
}

// resolve follows a PPtr from the file that holds it.
func (a *assets) resolve(from *loadedFile, ref any) (*loadedFile, Object, bool) {
	fileID, pathID := pptr(ref)
	if pathID == 0 {
		return nil, Object{}, false
	}
	target := from
	if fileID > 0 {
		if fileID > len(from.sf.Externals) {
			return nil, Object{}, false
		}
		target = a.byCAB[path.Base(from.sf.Externals[fileID-1])]
		if target == nil {
			return nil, Object{}, false
		}
	}
	o, ok := target.sf.Object(pathID)
	return target, o, ok
}

func vec(v any, keys ...string) []float64 {
	m, _ := v.(map[string]any)
	out := make([]float64, len(keys))
	for i, k := range keys {
		switch x := m[k].(type) {
		case float64:
			out[i] = x
		case int64:
			out[i] = float64(x)
		}
	}
	return out
}

// ---- Mesh vertex data (Unity 2019) ----

var vertexFormatSize = [12]int{4, 2, 1, 1, 2, 2, 1, 1, 2, 2, 4, 4}

type channel struct{ stream, offset, format, dimension int }

type meshData struct {
	positions, normals [][3]float32
	uvs                [][2]float32
	joints             [][4]uint16
	weights            [][4]float32
	triangles          []uint32
	bindPoses          [][16]float64
}

func readComponent(b []byte, format int) float32 {
	switch format {
	case 0:
		return math.Float32frombits(binary.LittleEndian.Uint32(b))
	case 1:
		return fp16ToFloat(binary.LittleEndian.Uint16(b))
	case 2:
		return float32(b[0]) / 255
	case 3:
		return max(float32(int8(b[0]))/127, -1)
	case 4:
		return float32(binary.LittleEndian.Uint16(b)) / 65535
	case 5:
		return max(float32(int16(binary.LittleEndian.Uint16(b)))/32767, -1)
	case 6:
		return float32(b[0])
	case 7:
		return float32(int8(b[0]))
	case 8:
		return float32(binary.LittleEndian.Uint16(b))
	case 9:
		return float32(int16(binary.LittleEndian.Uint16(b)))
	case 10:
		return float32(binary.LittleEndian.Uint32(b))
	case 11:
		return float32(int32(binary.LittleEndian.Uint32(b)))
	}
	return 0
}

func decodeMesh(fields map[string]any) (*meshData, error) {
	if num(fields["m_MeshCompression"]) != 0 {
		return nil, errors.New("compressed meshes are not supported")
	}
	vd, _ := fields["m_VertexData"].(map[string]any)
	count := num(vd["m_VertexCount"])
	data, _ := vd["m_DataSize"].([]byte)
	rawChannels, _ := vd["m_Channels"].([]any)
	channels := make([]channel, len(rawChannels))
	streams := 0
	for i, c := range rawChannels {
		cm, _ := c.(map[string]any)
		channels[i] = channel{num(cm["stream"]), num(cm["offset"]), num(cm["format"]), num(cm["dimension"]) & 0xf}
		if channels[i].dimension > 0 {
			streams = max(streams, channels[i].stream+1)
		}
	}
	strides := make([]int, streams)
	for _, c := range channels {
		if c.dimension > 0 && c.format < len(vertexFormatSize) {
			strides[c.stream] += c.dimension * vertexFormatSize[c.format]
		}
	}
	offsets := make([]int, streams)
	for s, at := 0, 0; s < streams; s++ {
		offsets[s] = at
		at += count * strides[s]
		at = (at + 15) &^ 15
	}
	get := func(ch, v, comp int) (float32, bool) {
		if ch >= len(channels) || channels[ch].dimension <= comp {
			return 0, false
		}
		c := channels[ch]
		size := vertexFormatSize[c.format]
		at := offsets[c.stream] + v*strides[c.stream] + c.offset + comp*size
		if at+size > len(data) {
			return 0, false
		}
		return readComponent(data[at:], c.format), true
	}
	m := &meshData{}
	for v := 0; v < count; v++ {
		var p, n [3]float32
		var uv [2]float32
		for i := 0; i < 3; i++ {
			p[i], _ = get(0, v, i)
			n[i], _ = get(1, v, i)
		}
		uv[0], _ = get(4, v, 0)
		uv[1], _ = get(4, v, 1)
		p[0], n[0] = -p[0], -n[0]
		uv[1] = 1 - uv[1]
		m.positions = append(m.positions, p)
		m.normals = append(m.normals, n)
		m.uvs = append(m.uvs, uv)
		var j [4]uint16
		var w [4]float32
		dimW := 0
		if len(channels) > 12 {
			dimW = channels[12].dimension
		}
		sum := float32(0)
		for i := 0; i < 4; i++ {
			if idx, ok := get(13, v, i); ok {
				j[i] = uint16(idx)
			}
			if i < dimW {
				w[i], _ = get(12, v, i)
				sum += w[i]
			}
		}
		if dimW > 0 && dimW < 4 {
			w[dimW] = max(0, 1-sum) // Unity drops the last weight when it can be derived
			sum += w[dimW]
		}
		if sum > 0 {
			for i := range w {
				w[i] /= sum
			}
		} else {
			w[0] = 1
		}
		for i := range w {
			if w[i] == 0 {
				j[i] = 0
			}
		}
		m.joints = append(m.joints, j)
		m.weights = append(m.weights, w)
	}
	indexData, _ := fields["m_IndexBuffer"].([]byte)
	wide := num(fields["m_IndexFormat"]) == 1
	index := func(i int) uint32 {
		if wide {
			return binary.LittleEndian.Uint32(indexData[i*4:])
		}
		return uint32(binary.LittleEndian.Uint16(indexData[i*2:]))
	}
	width := 2
	if wide {
		width = 4
	}
	subMeshes, _ := fields["m_SubMeshes"].([]any)
	for _, s := range subMeshes {
		sm, _ := s.(map[string]any)
		if num(sm["topology"]) != 0 {
			continue
		}
		first, n, base := num(sm["firstByte"])/width, num(sm["indexCount"]), num(sm["baseVertex"])
		if (first+n)*width > len(indexData) {
			return nil, errors.New("index buffer is cut short")
		}
		for i := 0; i+2 < n; i += 3 {
			a, b, c := index(first+i)+uint32(base), index(first+i+1)+uint32(base), index(first+i+2)+uint32(base)
			if int(max(a, b, c)) >= count {
				return nil, errors.New("triangle points past the vertices")
			}
			m.triangles = append(m.triangles, a, c, b)
		}
	}
	poses, _ := fields["m_BindPose"].([]any)
	for _, p := range poses {
		e := vec(p, "e00", "e01", "e02", "e03", "e10", "e11", "e12", "e13", "e20", "e21", "e22", "e23", "e30", "e31", "e32", "e33")
		// Mirror X on both sides (S·M·S), then store column-major as glTF wants.
		sign := [4]float64{-1, 1, 1, 1}
		var col [16]float64
		for r := 0; r < 4; r++ {
			for c := 0; c < 4; c++ {
				col[c*4+r] = e[r*4+c] * sign[r] * sign[c]
			}
		}
		m.bindPoses = append(m.bindPoses, col)
	}
	return m, nil
}

// ---- glTF writing ----

type gltfBuilder struct {
	doc map[string]any
	bin bytes.Buffer
	acc []any
	bv  []any
}

func (g *gltfBuilder) view(data []byte, target int) int {
	for g.bin.Len()%4 != 0 {
		g.bin.WriteByte(0)
	}
	v := map[string]any{"buffer": 0, "byteOffset": g.bin.Len(), "byteLength": len(data)}
	if target != 0 {
		v["target"] = target
	}
	g.bin.Write(data)
	g.bv = append(g.bv, v)
	return len(g.bv) - 1
}

func (g *gltfBuilder) accessor(data []byte, componentType, count int, kind string, target int, extra map[string]any) int {
	a := map[string]any{"bufferView": g.view(data, target), "componentType": componentType, "count": count, "type": kind}
	for k, v := range extra {
		a[k] = v
	}
	g.acc = append(g.acc, a)
	return len(g.acc) - 1
}

func floats2(items [][2]float32) []byte { return le(items) }
func floats3(items [][3]float32) []byte { return le(items) }
func floats4(items [][4]float32) []byte { return le(items) }

func le(v any) []byte {
	var buf bytes.Buffer
	binary.Write(&buf, binary.LittleEndian, v)
	return buf.Bytes()
}

// ModelOptions limits texture sizes.
type ModelOptions struct{ MaxTexture int }

// CostumeToGLB converts the costume in actorFolder (…/3d/actor/ch008001) to a .glb at target.
func CostumeToGLB(actorFolder, target string, opt ModelOptions) error {
	asset := filepath.Base(actorFolder)
	a, err := openAssets(actorFolder)
	if err != nil {
		return err
	}
	skeleton := a.byCABOfBundle(filepath.Join(actorFolder, "mesh", "sk_"+asset+".assetbundle"))
	if skeleton == nil {
		// Some weapon variants carry only their prefab, with the mesh in a sibling's skeleton
		// bundle (wp005528 draws wp005505's): load the family's skeletons so it resolves.
		skeleton = a.byCABOfBundle(filepath.Join(actorFolder, "mesh", asset+".assetbundle"))
		if skeleton == nil || len(asset) < 6 {
			return errors.New("this costume has no skeleton bundle")
		}
		// The family first (wp0055*); a few borrow from another series of the same type (wp006011
		// draws wp006520's), so widen to the type (wp006*) while anything is still missing.
		for _, prefix := range []string{asset[:6], asset[:5]} {
			if a.hasAll(skeleton.sf.Externals) {
				break
			}
			siblings, _ := filepath.Glob(filepath.Join(filepath.Dir(actorFolder), prefix+"*", "mesh", "sk_*.assetbundle"))
			for _, f := range siblings {
				if a.byCABOfBundle(f) == nil {
					_ = a.add(f) // a sibling that will not open only matters if this model needed it
				}
			}
		}
	}
	// An enemy's other looks keep their own material but draw its textures from the family's first
	// look (mt008101's fire body uses mt008001's): load the family's textures, one at a time, while
	// anything a loaded bundle points to is still missing.
	if len(asset) >= 6 {
		for _, prefix := range []string{asset[:6], asset[:5]} {
			if a.complete() {
				break
			}
			files, _ := filepath.Glob(filepath.Join(filepath.Dir(actorFolder), prefix+"*", "texture", "*.assetbundle"))
			for _, f := range files {
				if a.byCABOfBundle(f) == nil {
					_ = a.add(f)
					if a.complete() {
						break
					}
				}
			}
		}
	}
	g := &gltfBuilder{doc: map[string]any{"asset": map[string]any{"version": "2.0", "generator": "Bunker Archive"}}}

	// Nodes: every Transform, named by its GameObject.
	transforms, err := skeleton.sf.Objects(classIDs["Transform"])
	if err != nil {
		return err
	}
	nodeOf := map[int64]int{}
	for i, t := range transforms {
		nodeOf[t.PathID] = i
	}
	nodes := make([]map[string]any, len(transforms))
	var roots []int
	for i, t := range transforms {
		name := ""
		if _, goObj, ok := a.resolve(skeleton, t.Fields["m_GameObject"]); ok {
			name, _ = goObj.Fields["m_Name"].(string)
		}
		p := vec(t.Fields["m_LocalPosition"], "x", "y", "z")
		q := vec(t.Fields["m_LocalRotation"], "x", "y", "z", "w")
		s := vec(t.Fields["m_LocalScale"], "x", "y", "z")
		n := map[string]any{"name": name, "translation": []float64{-p[0], p[1], p[2]},
			"rotation": []float64{q[0], -q[1], -q[2], q[3]}, "scale": s}
		var children []int
		if list, ok := t.Fields["m_Children"].([]any); ok {
			for _, c := range list {
				if _, id := pptr(c); id != 0 {
					if ci, ok := nodeOf[id]; ok {
						children = append(children, ci)
					}
				}
			}
		}
		if len(children) > 0 {
			n["children"] = children
		}
		nodes[i] = n
		if _, father := pptr(t.Fields["m_Father"]); father == 0 {
			roots = append(roots, i)
		}
	}

	renderers, err := skeleton.sf.Objects(classIDs["SkinnedMeshRenderer"])
	if err != nil {
		return err
	}
	var meshes, skins, materials, textures, images []any
	materialOf := map[int64]int{}
	for _, r := range renderers {
		if enabled, _ := r.Fields["m_Enabled"].(bool); !enabled {
			continue
		}
		_, meshObj, ok := a.resolve(skeleton, r.Fields["m_Mesh"])
		if !ok {
			continue
		}
		m, err := decodeMesh(meshObj.Fields)
		if err != nil || len(m.triangles) == 0 {
			continue
		}
		bones, _ := r.Fields["m_Bones"].([]any)
		joints := make([]int, len(bones))
		for i, b := range bones {
			_, id := pptr(b)
			joints[i] = nodeOf[id]
		}
		if len(m.bindPoses) != len(joints) {
			continue
		}
		// Material and its colour texture.
		mat := -1
		if list, ok := r.Fields["m_Materials"].([]any); ok && len(list) > 0 {
			if matFile, matObj, ok := a.resolve(skeleton, list[0]); ok {
				if i, seen := materialOf[matObj.PathID]; seen {
					mat = i
				} else {
					mat = len(materials)
					materialOf[matObj.PathID] = mat
					materials = append(materials, g.material(a, matFile, matObj, &textures, &images, opt))
				}
			}
		}
		var bounds [2][3]float32
		for i, p := range m.positions {
			for k := 0; k < 3; k++ {
				if i == 0 || p[k] < bounds[0][k] {
					bounds[0][k] = p[k]
				}
				if i == 0 || p[k] > bounds[1][k] {
					bounds[1][k] = p[k]
				}
			}
		}
		pos := g.accessor(floats3(m.positions), 5126, len(m.positions), "VEC3", 34962,
			map[string]any{"min": bounds[0][:], "max": bounds[1][:]})
		norm := g.accessor(floats3(m.normals), 5126, len(m.normals), "VEC3", 34962, nil)
		uv := g.accessor(floats2(m.uvs), 5126, len(m.uvs), "VEC2", 34962, nil)
		var jb bytes.Buffer
		for _, j := range m.joints {
			binary.Write(&jb, binary.LittleEndian, j)
		}
		jo := g.accessor(jb.Bytes(), 5123, len(m.joints), "VEC4", 34962, nil)
		we := g.accessor(floats4(m.weights), 5126, len(m.weights), "VEC4", 34962, nil)
		var ib bytes.Buffer
		binary.Write(&ib, binary.LittleEndian, m.triangles)
		idx := g.accessor(ib.Bytes(), 5125, len(m.triangles), "SCALAR", 34963, nil)
		var bp bytes.Buffer
		for _, mtx := range m.bindPoses {
			for _, f := range mtx {
				binary.Write(&bp, binary.LittleEndian, float32(f))
			}
		}
		ibm := g.accessor(bp.Bytes(), 5126, len(m.bindPoses), "MAT4", 0, nil)
		prim := map[string]any{"attributes": map[string]any{"POSITION": pos, "NORMAL": norm, "TEXCOORD_0": uv, "JOINTS_0": jo, "WEIGHTS_0": we}, "indices": idx}
		if mat >= 0 {
			prim["material"] = mat
		}
		name, _ := meshObj.Fields["m_Name"].(string)
		meshes = append(meshes, map[string]any{"name": name, "primitives": []any{prim}})
		skin := map[string]any{"joints": joints, "inverseBindMatrices": ibm}
		if len(roots) > 0 {
			skin["skeleton"] = roots[0]
		}
		skins = append(skins, skin)
		nodes = append(nodes, map[string]any{"name": name, "mesh": len(meshes) - 1, "skin": len(skins) - 1})
		roots = append(roots, len(nodes)-1)
	}
	if len(meshes) == 0 {
		return errors.New("no meshes could be read")
	}
	sort.Ints(roots)
	g.doc["scene"] = 0
	g.doc["scenes"] = []any{map[string]any{"nodes": roots}}
	g.doc["nodes"] = nodes
	g.doc["meshes"] = meshes
	g.doc["skins"] = skins
	if len(materials) > 0 {
		g.doc["materials"] = materials
	}
	if len(textures) > 0 {
		g.doc["textures"] = textures
		g.doc["images"] = images
		g.doc["samplers"] = []any{map[string]any{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}}
	}
	return g.writeGLB(target)
}

// hasAll reports whether every external bundle file (archive:/CAB-…/CAB-…) is loaded;
// Unity's built-in resources never are and do not count.
func (a *assets) hasAll(externals []string) bool {
	for _, e := range externals {
		if name := path.Base(e); strings.HasPrefix(name, "CAB-") && a.byCAB[name] == nil {
			return false
		}
	}
	return true
}

// complete reports whether every loaded file's external bundles are loaded too.
func (a *assets) complete() bool {
	for _, f := range a.byCAB {
		if !a.hasAll(f.sf.Externals) {
			return false
		}
	}
	return true
}

func (a *assets) byCABOfBundle(bundlePath string) *loadedFile {
	for _, f := range a.byCAB {
		if filepath.Clean(f.path) == filepath.Clean(bundlePath) {
			return f
		}
	}
	return nil
}

func (g *gltfBuilder) material(a *assets, file *loadedFile, mat Object, textures, images *[]any, opt ModelOptions) map[string]any {
	name, _ := mat.Fields["m_Name"].(string)
	keywords, _ := mat.Fields["m_ShaderKeywords"].(string)
	out := map[string]any{"name": name, "doubleSided": true,
		"pbrMetallicRoughness": map[string]any{"metallicFactor": 0.0, "roughnessFactor": 1.0}}
	if strings.Contains(keywords, "_ALPHATEST_ON") {
		out["alphaMode"] = "MASK"
		out["alphaCutoff"] = 0.5
	}
	props, _ := mat.Fields["m_SavedProperties"].(map[string]any)
	envs, _ := props["m_TexEnvs"].([]any)
	for _, e := range envs {
		pair, _ := e.(map[string]any)
		if pair["first"] != "_MainTex" {
			continue
		}
		env, _ := pair["second"].(map[string]any)
		texFile, tex, ok := a.resolve(file, env["m_Texture"])
		if !ok {
			break
		}
		png, err := texturePNG(texFile.bundle, tex, opt.MaxTexture)
		if err != nil {
			break
		}
		*images = append(*images, map[string]any{"bufferView": g.view(png, 0), "mimeType": "image/png"})
		*textures = append(*textures, map[string]any{"source": len(*images) - 1, "sampler": 0})
		out["pbrMetallicRoughness"].(map[string]any)["baseColorTexture"] = map[string]any{"index": len(*textures) - 1}
	}
	return out
}

// texturePNG decodes one Texture2D object to PNG.
func texturePNG(b *Bundle, tex Object, maxSide int) ([]byte, error) {
	w, h := num(tex.Fields["m_Width"]), num(tex.Fields["m_Height"])
	data, err := imageData(b, tex.Fields)
	if err != nil {
		return nil, err
	}
	pixels, err := decodePixels(num(tex.Fields["m_TextureFormat"]), w, h, data)
	if err != nil {
		return nil, err
	}
	row := w * 4
	flipped := make([]byte, len(pixels))
	for y := 0; y < h; y++ {
		copy(flipped[y*row:(y+1)*row], pixels[(h-1-y)*row:(h-y)*row])
	}
	return Texture{Width: w, Height: h, RGBA: flipped}.Shrink(maxSide).PNG()
}

func (g *gltfBuilder) writeGLB(target string) error {
	for g.bin.Len()%4 != 0 {
		g.bin.WriteByte(0)
	}
	g.doc["buffers"] = []any{map[string]any{"byteLength": g.bin.Len()}}
	g.doc["bufferViews"] = g.bv
	g.doc["accessors"] = g.acc
	js, err := json.Marshal(g.doc)
	if err != nil {
		return err
	}
	for len(js)%4 != 0 {
		js = append(js, ' ')
	}
	var out bytes.Buffer
	total := 12 + 8 + len(js) + 8 + g.bin.Len()
	binary.Write(&out, binary.LittleEndian, []uint32{0x46546C67, 2, uint32(total), uint32(len(js)), 0x4E4F534A})
	out.Write(js)
	binary.Write(&out, binary.LittleEndian, []uint32{uint32(g.bin.Len()), 0x004E4942})
	out.Write(g.bin.Bytes())
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return err
	}
	pending := target + ".tmp"
	if err := os.WriteFile(pending, out.Bytes(), 0o644); err != nil {
		return err
	}
	return os.Rename(pending, target)
}
