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
	if err := ScenarioToJSON(filepath.Join(root, "eventmap/main"), out); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(out)
	var maps map[string][][3]any
	if err := json.Unmarshal(data, &maps); err != nil {
		t.Fatal(err)
	}
	total := 0
	for _, l := range maps {
		total += len(l)
	}
	if len(maps) < 1000 || total < 7000 {
		t.Fatalf("%d maps, %d lines", len(maps), total)
	}
	t.Logf("%d event maps, %d lines", len(maps), total)
}
