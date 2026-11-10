package translation

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"
)

func readStatus(t *testing.T, r roots) Status {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(r.asset, "translation", "status.json"))
	if err != nil {
		t.Fatal(err)
	}
	var s Status
	if err := json.Unmarshal(data, &s); err != nil {
		t.Fatal(err)
	}
	return s
}

func TestStatusOff(t *testing.T) {
	r := newRoots(t)
	tr := start(t, r, translateUI)
	tr.wait()
	if s := readStatus(t, r); s.State != "off" {
		t.Fatalf("%+v", s)
	}
}

func TestStatusReady(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	tr := start(t, r, translateUI)
	tr.wait()
	if s := readStatus(t, r); s.State != "ready" || s.Language != "pt" || s.Bundles != 1 || s.Error != "" {
		t.Fatalf("%+v", s)
	}
}

func TestStatusBuilding(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	release := make(chan struct{})
	tr := start(t, r, func(raw []byte, name string, values map[string]string) ([]byte, uint32, bool, error) {
		<-release
		return translateUI(raw, name, values)
	})
	if s := readStatus(t, r); s.State != "building" || s.Language != "pt" {
		t.Fatalf("%+v", s)
	}
	close(release)
	tr.wait()
}

func TestStatusInvalidPack(t *testing.T) {
	r := newRoots(t)
	if err := writeFileAtomic(filepath.Join(r.asset, "translation/active.json"), []byte(`{"format":9}`), 0644); err != nil {
		t.Fatal(err)
	}
	tr := start(t, r, translateUI)
	tr.wait()
	if s := readStatus(t, r); s.State != "failed" || s.Error == "" {
		t.Fatalf("%+v", s)
	}
}

// failingBuild fails its first n calls (as a full disk would), then builds.
func failingBuild(n int32, calls *atomic.Int32) buildFunc {
	return func(assets string, list []Entry, listMD5 string, pack *Pack, dir string, rebuild Rebuilder) (*Manifest, error) {
		if calls.Add(1) <= n {
			return nil, errors.New("no space left on device")
		}
		return Build(assets, list, listMD5, pack, dir, rebuild)
	}
}

func TestBuildRetriedAfterFailure(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	var calls atomic.Int32
	tr := New(r.asset, r.data, "android")
	tr.rebuild, tr.build, tr.retryDelays = translateUI, failingBuild(1, &calls), []time.Duration{0}
	tr.Start()
	tr.wait()
	if s := readStatus(t, r); s.State != "ready" || calls.Load() != 2 {
		t.Fatalf("%+v after %d calls", s, calls.Load())
	}
	if revision, _ := listOf(t, get(t, tr.Wrap(next(r)), listURL)); revision != 1817 {
		t.Fatalf("revision %d", revision)
	}
}

func TestBuildGivesUpAfterRetries(t *testing.T) {
	r := newRoots(t)
	r.setPack(t, "um")
	var calls atomic.Int32
	tr := New(r.asset, r.data, "android")
	tr.rebuild, tr.build, tr.retryDelays = translateUI, failingBuild(100, &calls), []time.Duration{0, 0}
	tr.Start()
	tr.wait()
	s := readStatus(t, r)
	if s.State != "failed" || s.Error != "no space left on device" || s.Attempts != 3 || calls.Load() != 3 {
		t.Fatalf("%+v after %d calls", s, calls.Load())
	}
}
