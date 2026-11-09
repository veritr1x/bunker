package translation

import (
	"crypto/md5"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
)

const englishTextPrefix = "text)en)"

// Manifest is a finished build: the list entries of the translated bundles
// (by object id) and the bundles that could not be translated.
type Manifest struct {
	ID       string           `json:"id"`
	PackHash string           `json:"packHash"`
	ListMD5  string           `json:"listMD5"`
	Entries  map[string]Entry `json:"entries"`
	Skipped  []string         `json:"skipped"`
}

// BuildID names the build of one pack for one list.bin.
func BuildID(packHash, listMD5 string) string {
	sum := sha256.Sum256([]byte(packHash + ":" + listMD5 + ":1"))
	return hex.EncodeToString(sum[:])[:16]
}

// Rebuilder translates one masked bundle; changed is false when none of its
// keys has a translation.
type Rebuilder func(raw []byte, name string, values map[string]string) (out []byte, crc uint32, changed bool, err error)

// DefaultRebuilder replaces the values of translated keys in every TextAsset.
func DefaultRebuilder(raw []byte, name string, values map[string]string) ([]byte, uint32, bool, error) {
	return RebuildText(raw, name, func(text string) (string, bool) {
		text, n := ReplaceValues(text, values)
		return text, n > 0
	})
}

// Build translates every English text bundle of list with the pack into dir:
// <objectID>.assetbundle for each bundle that changed, then manifest.json
// (written last: a build without it is unfinished). assetsRevision is the
// folder holding assetbundle/. A bundle that is missing or fails keeps its
// English and is listed in Skipped.
func Build(assetsRevision string, list []Entry, listMD5 string, pack *Pack, dir string, rebuild Rebuilder) (*Manifest, error) {
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, err
	}
	m := &Manifest{ID: BuildID(pack.Hash, listMD5), PackHash: pack.Hash, ListMD5: listMD5, Entries: map[string]Entry{}, Skipped: []string{}}
	for _, e := range list {
		if !strings.HasPrefix(e.Path, englishTextPrefix) {
			continue
		}
		file := filepath.Join(assetsRevision, "assetbundle", strings.ReplaceAll(e.Path, ")", "/")+".assetbundle")
		raw, err := os.ReadFile(file)
		var out []byte
		var crc uint32
		changed := false
		if err == nil {
			out, crc, changed, err = rebuild(raw, e.Path, pack.Game)
		}
		if err != nil {
			log.Printf("[Translation] %s keeps its English: %v", e.Path, err)
			m.Skipped = append(m.Skipped, e.Path)
			continue
		}
		if !changed {
			continue
		}
		if err := writeFileAtomic(filepath.Join(dir, e.ObjectID+".assetbundle"), out, 0644); err != nil {
			return nil, err
		}
		sum := md5.Sum(out)
		m.Entries[e.ObjectID] = Entry{ObjectID: e.ObjectID, Path: e.Path, Size: uint64(len(out)), CRC: crc, MD5: hex.EncodeToString(sum[:])}
	}
	data, err := json.Marshal(m)
	if err != nil {
		return nil, err
	}
	if err := writeFileAtomic(filepath.Join(dir, "manifest.json"), data, 0644); err != nil {
		return nil, err
	}
	return m, nil
}

// LoadManifest reads a finished build's manifest.
func LoadManifest(dir string) (*Manifest, error) {
	data, err := os.ReadFile(filepath.Join(dir, "manifest.json"))
	if err != nil {
		return nil, err
	}
	var m Manifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("manifest: %w", err)
	}
	return &m, nil
}
