package unityasset

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// Event maps name who says each main-story line: one line per node, or several.
func TestScenarioLines(t *testing.T) {
	root := dumpRoot(t)
	lines, err := ScenarioLines(filepath.Join(root, "eventmap/main/0201002001020c.assetbundle"))
	if err != nil {
		t.Fatal(err)
	}
	found := map[string]ScenarioLine{}
	for _, l := range lines {
		found[l.Key] = l
	}
	// Hina (actor object 19008) in a multi-line node and in a single-line node.
	if l := found["MID_b010_0020g_00900_01060_1"]; l.Actor != 19008 {
		t.Fatalf("multi-line node: %+v", l)
	}
	if l := found["MID_b010_0020g_01000_01080_1"]; l.Key == "" {
		t.Fatal("single-line node missing")
	}
	out := filepath.Join(t.TempDir(), "scenario.json")
	if err := ScenarioToJSON(filepath.Join(root, "eventmap"), out); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(out)
	var maps map[string]EventMap
	if err := json.Unmarshal(data, &maps); err != nil {
		t.Fatal(err)
	}
	total := 0
	for _, m := range maps {
		total += len(m.Lines)
	}
	if len(maps) < 1000 || total < 7000 {
		t.Fatalf("%d maps, %d lines", len(maps), total)
	}
	// A Dark Memory's map names the text it reads.
	if paths := maps["endcontents/0005003000001n"].Paths; len(paths) == 0 || paths[0] != "sub)season01)eid_a01040_1010g" {
		t.Fatalf("endcontents paths %v", paths)
	}
	// And the music it starts: Hina's first scenes in The Cage play track 1071, stem 2.
	if music := maps["main/0201002001020c"].Music; len(music) == 0 || music[0] != [2]int{1071, 2} {
		t.Fatalf("music %v", music)
	}
	t.Logf("%d event maps, %d lines", len(maps), total)
}
