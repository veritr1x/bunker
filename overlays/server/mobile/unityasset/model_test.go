package unityasset

import (
	"encoding/binary"
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// readGLB checks a .glb's framing and returns its JSON.
func readGLB(t *testing.T, path string) map[string]any {
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(data) < 20 || binary.LittleEndian.Uint32(data) != 0x46546C67 || int(binary.LittleEndian.Uint32(data[8:])) != len(data) {
		t.Fatal("bad GLB header")
	}
	n := int(binary.LittleEndian.Uint32(data[12:]))
	var doc map[string]any
	if err := json.Unmarshal(data[20:20+n], &doc); err != nil {
		t.Fatal(err)
	}
	bin := data[20+n:]
	if int(binary.LittleEndian.Uint32(bin)) != len(bin)-8 {
		t.Fatal("bad binary chunk")
	}
	return doc
}

func dumpRoot(t *testing.T) string {
	dump := os.Getenv("ARCHIVE_DUMP")
	if dump == "" {
		t.Skip("set ARCHIVE_DUMP to an extracted revisions/0")
	}
	return filepath.Join(dump, "assetbundle")
}

// Every skin's joints and inverse bind matrices agree, every accessor fits its view,
// and positions carry bounds; on one costume, or all of them with ARCHIVE_ALL_MODELS.
func TestCostumeToGLB(t *testing.T) {
	root := dumpRoot(t)
	folders := []string{filepath.Join(root, "3d/actor/ch008001")}
	if os.Getenv("ARCHIVE_ALL_MODELS") != "" {
		folders, _ = filepath.Glob(filepath.Join(root, "3d/actor/ch[0-9][0-9][0-9][0-9][0-9][0-9]"))
	}
	failed, bare := 0, 0
	for _, folder := range folders {
		if _, err := os.Stat(filepath.Join(folder, "mesh", "sk_"+filepath.Base(folder)+".assetbundle")); err != nil {
			continue
		}
		out := filepath.Join(t.TempDir(), "m.glb")
		if err := CostumeToGLB(folder, out, ModelOptions{MaxTexture: 256}); err != nil {
			t.Errorf("%s: %v", filepath.Base(folder), err)
			failed++
			continue
		}
		doc := readGLB(t, out)
		accessors, _ := doc["accessors"].([]any)
		views, _ := doc["bufferViews"].([]any)
		for _, s := range doc["skins"].([]any) {
			skin := s.(map[string]any)
			ibm := accessors[int(skin["inverseBindMatrices"].(float64))].(map[string]any)
			if int(ibm["count"].(float64)) != len(skin["joints"].([]any)) {
				t.Fatalf("%s: skin joints and bind matrices differ", folder)
			}
		}
		sizes := map[string]int{"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
		widths := map[float64]int{5123: 2, 5125: 4, 5126: 4}
		for _, a := range accessors {
			acc := a.(map[string]any)
			view := views[int(acc["bufferView"].(float64))].(map[string]any)
			need := int(acc["count"].(float64)) * sizes[acc["type"].(string)] * widths[acc["componentType"].(float64)]
			if need > int(view["byteLength"].(float64)) {
				t.Fatalf("%s: accessor larger than its view", folder)
			}
		}
		if meshes, _ := doc["meshes"].([]any); len(meshes) == 0 {
			t.Fatalf("%s: no meshes", folder)
		}
		if materials, _ := doc["materials"].([]any); len(materials) == 0 {
			t.Logf("%s: no materials", filepath.Base(folder))
			bare++
		}
	}
	t.Logf("%d costumes: %d failed, %d without materials", len(folders), failed, bare)
}

// A run cycle: bones named as in the model, finite values, unit rotations, and the
// root kept in place.
func TestClipToJSON(t *testing.T) {
	root := dumpRoot(t)
	actor := filepath.Join(root, "3d/actor/ch008001")
	out := filepath.Join(t.TempDir(), "run.json")
	if err := ClipToJSON(filepath.Join(root, "3d/motion/ch008/general/anim_tw_ch008_run_01_lp.assetbundle"), actor, out, 30); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(out)
	var clip Clip
	if err := json.Unmarshal(data, &clip); err != nil {
		t.Fatal(err)
	}
	if clip.Duration <= 0 || len(clip.Tracks) < 50 {
		t.Fatalf("duration %v, %d tracks", clip.Duration, len(clip.Tracks))
	}
	legMoves := false
	for _, tr := range clip.Tracks {
		width := 3
		if tr.Type == "quaternion" {
			width = 4
		}
		if len(tr.Values) != len(tr.Times)*width {
			t.Fatalf("%s: %d values for %d times", tr.Name, len(tr.Values), len(tr.Times))
		}
		for i, v := range tr.Values {
			if math.IsNaN(float64(v)) || math.IsInf(float64(v), 0) {
				t.Fatalf("%s: value %d is not finite", tr.Name, i)
			}
		}
		if width == 4 {
			for i := 0; i < len(tr.Values); i += 4 {
				l := math.Sqrt(float64(tr.Values[i]*tr.Values[i] + tr.Values[i+1]*tr.Values[i+1] + tr.Values[i+2]*tr.Values[i+2] + tr.Values[i+3]*tr.Values[i+3]))
				if math.Abs(l-1) > 1e-3 {
					t.Fatalf("%s: rotation length %v", tr.Name, l)
				}
			}
		}
		if tr.Name == "root.position" {
			for i := 0; i < len(tr.Values); i += 3 {
				if tr.Values[i] != tr.Values[0] || tr.Values[i+2] != tr.Values[2] {
					t.Fatal("root motion is not kept in place")
				}
			}
		}
		if strings.HasPrefix(tr.Name, "left_upleg.") {
			first, last := tr.Values[:4], tr.Values[len(tr.Values)/2:len(tr.Values)/2+4]
			legMoves = math.Abs(float64(first[0]-last[0]))+math.Abs(float64(first[1]-last[1])) > 0.05
		}
	}
	if !legMoves {
		t.Fatal("the run cycle does not move the legs")
	}
}

// Without an Avatar, the skeleton's own paths stand in: they must name every path an Avatar would.
func TestHierarchyPaths(t *testing.T) {
	root := dumpRoot(t)
	skeleton := filepath.Join(root, "3d/actor/ch008001/mesh/sk_ch008001.assetbundle")
	a := &assets{byCAB: map[string]*loadedFile{}}
	if err := a.add(skeleton); err != nil {
		t.Fatal(err)
	}
	file := a.byCABOfBundle(skeleton)
	fromAvatar, err := avatarPaths(a, file)
	if err != nil {
		t.Fatal(err)
	}
	fromSkeleton, err := hierarchyPaths(a, file)
	if err != nil {
		t.Fatal(err)
	}
	for crc, path := range fromAvatar {
		if fromSkeleton[crc] != path {
			t.Fatalf("avatar path %q (%d) is %q from the skeleton", path, crc, fromSkeleton[crc])
		}
	}
	// ch010003 has no Avatar; its motions convert all the same.
	out := filepath.Join(t.TempDir(), "idle.json")
	if err := ClipToJSON(filepath.Join(root, "3d/motion/ch010/general/anim_bt_ch010_avoid_01.assetbundle"), filepath.Join(root, "3d/actor/ch010003"), out, 30); err != nil {
		t.Fatal(err)
	}
}
