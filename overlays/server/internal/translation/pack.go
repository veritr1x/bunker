package translation

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
)

// MaxPackBytes is the largest pack file read.
const MaxPackBytes = 64 << 20

// Pack is a language pack's game text. A pack comes from strangers: only these
// fields are read, and nothing in it names a file.
type Pack struct {
	Language, Name, Version string
	Hash                    string // hex sha256 of the file
	Game                    map[string]string
	Dropped                 int // values left out: empty, not text, or with a line break
}

// LoadPack reads a pack file (format 1). Values that are empty (shown in
// English), not strings, or contain a line break (which would split the
// game's key:value line) are left out and counted.
func LoadPack(path string) (*Pack, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, MaxPackBytes+1))
	if err != nil {
		return nil, err
	}
	if len(data) > MaxPackBytes {
		return nil, fmt.Errorf("pack is larger than %d MB", MaxPackBytes>>20)
	}
	var raw struct {
		Format   int                        `json:"format"`
		Language string                     `json:"language"`
		Name     string                     `json:"name"`
		Version  string                     `json:"version"`
		Game     map[string]json.RawMessage `json:"game"`
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("pack is not valid: %w", err)
	}
	if raw.Format != 1 {
		return nil, fmt.Errorf("pack format %d is not supported", raw.Format)
	}
	if strings.TrimSpace(raw.Language) == "" {
		return nil, errors.New("pack has no language")
	}
	sum := sha256.Sum256(data)
	p := &Pack{Language: raw.Language, Name: raw.Name, Version: raw.Version, Hash: hex.EncodeToString(sum[:]), Game: map[string]string{}}
	for key, value := range raw.Game {
		var s string
		if json.Unmarshal(value, &s) != nil || s == "" || strings.ContainsAny(s, "\r\n") {
			p.Dropped++
			continue
		}
		p.Game[key] = s
	}
	return p, nil
}
