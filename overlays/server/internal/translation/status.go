package translation

import (
	"encoding/json"
	"log"
)

// Status is what the translation is doing, kept in
// <assetRoot>/translation/status.json for Pod Programs to show.
type Status struct {
	State    string   `json:"state"` // off, building, ready or failed
	Language string   `json:"language,omitempty"`
	Name     string   `json:"name,omitempty"`
	Version  string   `json:"version,omitempty"`
	Texts    int      `json:"texts,omitempty"`   // translated texts the pack gives
	Dropped  int      `json:"dropped,omitempty"` // texts left out (empty, not text, a line break)
	Bundles  int      `json:"bundles,omitempty"` // bundles translated
	Skipped  []string `json:"skipped,omitempty"` // bundles that keep their English
	Attempts int      `json:"attempts,omitempty"`
	Error    string   `json:"error,omitempty"`
}

func packStatus(state string, pack *Pack) Status {
	s := Status{State: state}
	if pack != nil {
		s.Language, s.Name, s.Version, s.Texts, s.Dropped = pack.Language, pack.Name, pack.Version, len(pack.Game), pack.Dropped
	}
	return s
}

func (t *Translator) setStatus(s Status) {
	data, err := json.Marshal(s)
	if err == nil {
		err = writeFileAtomic(t.statusPath, data, 0644)
	}
	if err != nil {
		log.Printf("[Translation] status not saved: %v", err)
	}
}
