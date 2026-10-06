package unityasset

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// ScenarioLine is one story line as an event map plays it: the line's text key, the
// actor it is attached to and, when the window names someone else, the speaker.
type ScenarioLine struct {
	Key     string
	Actor   int
	Speaker int
}

// ScenarioLines reads the story lines an event map bundle plays. Message nodes hold
// one line (_scenarioKey, _actorId) or several (_scenarioKeys with _textParamters).
func ScenarioLines(bundlePath string) ([]ScenarioLine, error) {
	b, err := OpenBundle(bundlePath)
	if err != nil {
		return nil, err
	}
	var out []ScenarioLine
	for name, data := range b.Files {
		if strings.HasSuffix(name, ".resS") || strings.HasSuffix(name, ".resource") {
			continue
		}
		sf, err := ParseSerializedFile(data)
		if err != nil {
			continue
		}
		for _, field := range []string{"_scenarioKey", "_scenarioKeys"} {
			nodes, err := sf.ObjectsWith(classIDs["MonoBehaviour"], field)
			if err != nil {
				return nil, err
			}
			for _, n := range nodes {
				out = append(out, messageLines(n.Fields)...)
			}
		}
	}
	return out, nil
}

func id(v any) int {
	m, _ := v.(map[string]any)
	return num(m["id"])
}

func messageLines(f map[string]any) []ScenarioLine {
	parameter, _ := f["_parameter"].(map[string]any)
	if key, _ := f["_scenarioKey"].(string); key != "" {
		return []ScenarioLine{{Key: key, Actor: id(f["_actorId"]), Speaker: id(parameter["SpeakerActorId"])}}
	}
	keys, _ := f["_scenarioKeys"].([]any)
	actors, _ := f["_textParamters"].([]any) // sic
	texts, _ := parameter["TextParameter"].([]any)
	var out []ScenarioLine
	for i, k := range keys {
		key, _ := k.(string)
		if key == "" {
			continue
		}
		line := ScenarioLine{Key: key}
		if i < len(actors) {
			a, _ := actors[i].(map[string]any)
			line.Actor = id(a["ActorId"])
		}
		if i < len(texts) {
			t, _ := texts[i].(map[string]any)
			line.Speaker = id(t["SpeakerActorId"])
		}
		out = append(out, line)
	}
	return out
}

// ScenarioToJSON writes {"event map file name": [[key, actor, speaker], …]} for every
// event map under dir that plays story lines, for the Archive's index.
func ScenarioToJSON(dir, target string) error {
	files, err := filepath.Glob(filepath.Join(dir, "*.assetbundle"))
	if err != nil {
		return err
	}
	sort.Strings(files)
	out := map[string][][3]any{}
	for _, f := range files {
		lines, err := ScenarioLines(f)
		if err != nil {
			continue // one unreadable map costs its own lines only
		}
		for _, l := range lines {
			name := strings.TrimSuffix(filepath.Base(f), ".assetbundle")
			out[name] = append(out[name], [3]any{l.Key, l.Actor, l.Speaker})
		}
	}
	data, err := json.Marshal(out)
	if err != nil {
		return err
	}
	return os.WriteFile(target, data, 0o644)
}
