package translation

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func writePack(t *testing.T, content string) string {
	path := filepath.Join(t.TempDir(), "pack.json")
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestLoadPack(t *testing.T) {
	path := writePack(t, `{"format":1,"language":"pt-BR","name":"Português","version":"1",
		"game":{"a":"x","b":"","c":"l1\nl2","d":7,"e":"r\rx"}}`)
	p, err := LoadPack(path)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(p.Game, map[string]string{"a": "x"}) || p.Dropped != 4 {
		t.Fatalf("game %v dropped %d", p.Game, p.Dropped)
	}
	if p.Language != "pt-BR" || p.Name != "Português" || p.Version != "1" || len(p.Hash) != 64 {
		t.Fatalf("%+v", p)
	}
}

func TestLoadPackRejects(t *testing.T) {
	for name, content := range map[string]string{
		"format 2":     `{"format":2,"language":"pt","game":{}}`,
		"no language":  `{"format":1,"game":{}}`,
		"not JSON":     `{"format":1,`,
		"game not map": `{"format":1,"language":"pt","game":[1]}`,
	} {
		if _, err := LoadPack(writePack(t, content)); err == nil {
			t.Errorf("%s: no error", name)
		}
	}
	big := filepath.Join(t.TempDir(), "big.json")
	if err := os.WriteFile(big, make([]byte, MaxPackBytes+1), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadPack(big); err == nil {
		t.Error("oversized pack: no error")
	}
}

func TestLoadPackIgnoresOtherFields(t *testing.T) {
	p, err := LoadPack(writePack(t, `{"format":1,"language":"pt","master":{"m.1":"x"},"bunker":{"b":"y"},"extra":[1],"game":{"a":"x"}}`))
	if err != nil || !reflect.DeepEqual(p.Game, map[string]string{"a": "x"}) {
		t.Fatalf("%v %v", p, err)
	}
}
