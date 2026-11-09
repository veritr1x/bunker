package bunkertext

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sync"
	"time"
)

// maxPack is the largest pack read (as translation.MaxPackBytes).
const maxPack = 64 << 20

var (
	mu      sync.Mutex
	active  string    // <asset root>/translation/active.json
	checked time.Time // when the file was last looked at: at most once a second
	stamp   string    // its size and time then
	current = newTexts(english, "en", nil)
	plain   = newTexts(english, "en", nil)
)

// SetActive names the active pack file (the one the translation server applies).
func SetActive(path string) {
	mu.Lock()
	defer mu.Unlock()
	active, checked, stamp = path, time.Time{}, ""
	current = plain
}

// For is the texts for a page the game shows in lang (ja, ko, en; "" is English): the active pack's
// on an English client, the English catalogue otherwise.
func For(lang string) *Texts {
	if lang != "en" && lang != "" {
		return plain
	}
	mu.Lock()
	defer mu.Unlock()
	if active == "" || time.Since(checked) < time.Second {
		return current
	}
	checked = time.Now()
	info, err := os.Stat(active)
	now := ""
	if err == nil {
		now = fmt.Sprintf("%d/%d", info.ModTime().UnixNano(), info.Size())
	}
	if now == stamp {
		return current
	}
	stamp = now
	current = load(active)
	return current
}

// load reads a pack; English when it is missing or cannot be read. Only text values are used.
func load(path string) *Texts {
	f, err := os.Open(path)
	if err != nil {
		return plain
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, maxPack+1))
	if err != nil || len(data) > maxPack {
		return plain
	}
	var raw struct {
		Language string                     `json:"language"`
		Bunker   map[string]json.RawMessage `json:"bunker"`
		Game     map[string]json.RawMessage `json:"game"`
		Master   map[string]json.RawMessage `json:"master"`
	}
	if json.Unmarshal(data, &raw) != nil || raw.Language == "" {
		return plain
	}
	t := newTexts(english, raw.Language, textsOf(raw.Bunker))
	t.game, t.master = textsOf(raw.Game), textsOf(raw.Master)
	return t
}

func textsOf(section map[string]json.RawMessage) map[string]string {
	out := map[string]string{}
	for k, v := range section {
		var s string
		if json.Unmarshal(v, &s) == nil && s != "" {
			out[k] = s
		}
	}
	return out
}
