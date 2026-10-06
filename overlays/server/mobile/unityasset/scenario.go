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
	lines, _, _, err := readEventMap(bundlePath)
	return lines, err
}

// readEventMap returns an event map's story lines, the text files it reads them from
// (_scenarioTextPathArray, like "sub)season01)eid_a01040_1010g") and the music it starts
// (_bgms: up to two [track, stem] pairs, bgm_1071_2 being track 1071, stem 2).
func readEventMap(bundlePath string) ([]ScenarioLine, []string, [][2]int, error) {
	b, err := OpenBundle(bundlePath)
	if err != nil {
		return nil, nil, nil, err
	}
	var out []ScenarioLine
	var paths []string
	var music [][2]int
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
				return nil, nil, nil, err
			}
			for _, n := range nodes {
				out = append(out, messageLines(n.Fields)...)
			}
		}
		maps, err := sf.ObjectsWith(classIDs["MonoBehaviour"], "_scenarioTextPathArray")
		if err != nil {
			return nil, nil, nil, err
		}
		for _, m := range maps {
			bgms, _ := m.Fields["_bgms"].(map[string]any)
			for _, slot := range []string{"_track1", "_track2"} {
				track, _ := bgms[slot].(map[string]any)
				if name := num(track["_name"]); name > 0 {
					music = append(music, [2]int{name, num(track["_stem"])})
				}
			}
			list, _ := m.Fields["_scenarioTextPathArray"].([]any)
			for _, p := range list {
				if path, _ := p.(string); path != "" {
					paths = append(paths, path)
				}
			}
		}
	}
	return out, paths, music, nil
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

// EventMap is what the Archive's index needs from one event map.
type EventMap struct {
	Lines [][3]any `json:"lines,omitempty"` // [key, actor, speaker]
	Paths []string `json:"paths,omitempty"`
	Music [][2]int `json:"music,omitempty"` // [track, stem]
}

// ScenarioToJSON writes {"folder/event map name": {"lines": [[key, actor, speaker], …],
// "paths": [text file, …]}} for every event map under dir (…/assetbundle/eventmap) that
// plays story text, for the Archive's index.
func ScenarioToJSON(dir, target string) error {
	files, err := filepath.Glob(filepath.Join(dir, "*", "*.assetbundle"))
	if err != nil {
		return err
	}
	sort.Strings(files)
	out := map[string]EventMap{}
	for _, f := range files {
		lines, paths, music, err := readEventMap(f)
		if err != nil || (len(lines) == 0 && len(paths) == 0 && len(music) == 0) {
			continue // one unreadable map costs its own lines only
		}
		m := EventMap{Paths: paths, Music: music}
		for _, l := range lines {
			m.Lines = append(m.Lines, [3]any{l.Key, l.Actor, l.Speaker})
		}
		name := filepath.Base(filepath.Dir(f)) + "/" + strings.TrimSuffix(filepath.Base(f), ".assetbundle")
		out[name] = m
	}
	data, err := json.Marshal(out)
	if err != nil {
		return err
	}
	return os.WriteFile(target, data, 0o644)
}
