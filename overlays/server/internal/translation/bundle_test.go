package translation

import (
	"bytes"
	"fmt"
	"math/rand"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"lunar-tear/server/mobile/unityasset"
)

// dumpRevision is an extracted revisions/0 (ARCHIVE_DUMP), or the test is skipped.
func dumpRevision(t *testing.T) string {
	dump := os.Getenv("ARCHIVE_DUMP")
	if dump == "" {
		t.Skip("set ARCHIVE_DUMP to an extracted revisions/0")
	}
	return dump
}

func readDumpBundle(t *testing.T, rel string) []byte {
	raw, err := os.ReadFile(filepath.Join(dumpRevision(t), "assetbundle", rel+".assetbundle"))
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

func TestMaskUnmaskRoundTrip(t *testing.T) {
	plain := make([]byte, 1000)
	rand.New(rand.NewSource(1)).Read(plain)
	copy(plain, "UnityFS")
	plain[0] = 'U'
	for _, marker := range []byte{0x31, 0x32} {
		masked := Mask(plain, "text)en)ui", marker)
		if masked[0] != marker {
			t.Fatalf("marker %x: first byte %x", marker, masked[0])
		}
		back, err := unityasset.Unmask(masked, "text)en)ui")
		if err != nil || !bytes.Equal(back, plain) {
			t.Fatalf("marker %x: round trip failed (%v)", marker, err)
		}
	}
}

func TestRebuildNoChange(t *testing.T) {
	raw := readDumpBundle(t, "text/en/gift")
	out, _, changed, err := RebuildText(raw, "text)en)gift", func(text string) (string, bool) { return text, false })
	if err != nil || changed || out != nil {
		t.Fatalf("changed=%v out=%d err=%v", changed, len(out), err)
	}
}

func TestRebuildKeepsSerializedFile(t *testing.T) {
	raw := readDumpBundle(t, "text/en/gift")
	_, crc, changed, err := RebuildText(raw, "text)en)gift", func(text string) (string, bool) { return text, true })
	if err != nil || !changed {
		t.Fatalf("changed=%v err=%v", changed, err)
	}
	if crc != 3054123202 { // list.bin's CRC for text)en)gift
		t.Fatalf("crc %d", crc)
	}
}

// A damaged bundle is an error, quickly and without a panic: never a hang or a huge allocation.
func TestRebuildDamagedBundles(t *testing.T) {
	raw := readDumpBundle(t, "text/en/gift")
	edit := func(text string) (string, bool) { return text + "x", true }
	try := func(label string, data []byte) {
		done := make(chan any, 1)
		go func() {
			defer func() { done <- recover() }()
			RebuildText(data, "text)en)gift", edit)
		}()
		select {
		case p := <-done:
			if p != nil {
				t.Fatalf("%s: panic %v", label, p)
			}
		case <-time.After(2 * time.Second):
			t.Fatalf("%s: still running after 2s", label)
		}
	}
	for _, n := range []int{0, 1, 8, 40, 60, 100, 300, len(raw) / 2, len(raw) - 1} {
		try(fmt.Sprintf("truncated to %d", n), raw[:n])
	}
	plain, err := unityasset.Unmask(raw, "text)en)gift")
	if err != nil {
		t.Fatal(err)
	}
	rng := rand.New(rand.NewSource(7))
	for i := 0; i < 400; i++ {
		damaged := bytes.Clone(plain)
		for j := 0; j < 1+rng.Intn(4); j++ {
			damaged[rng.Intn(len(damaged))] = byte(rng.Intn(256))
		}
		try(fmt.Sprintf("flip %d", i), Mask(damaged, "text)en)gift", raw[0]))
	}
	// the serialized file inside, damaged, behind an intact bundle header
	b, err := readBundle(plain)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 400; i++ {
		data := bytes.Clone(b.data)
		for j := 0; j < 1+rng.Intn(4); j++ {
			data[rng.Intn(4200)] = byte(rng.Intn(256))
		}
		done := make(chan any, 1)
		go func() {
			defer func() { done <- recover() }()
			rewriteTextAssets(data, edit)
		}()
		select {
		case p := <-done:
			if p != nil {
				t.Fatalf("serialized flip %d: panic %v", i, p)
			}
		case <-time.After(2 * time.Second):
			t.Fatalf("serialized flip %d: still running after 2s", i)
		}
	}
}

func TestRebuildChangesText(t *testing.T) {
	raw := readDumpBundle(t, "text/en/ui")
	out, _, changed, err := RebuildText(raw, "text)en)ui", func(text string) (string, bool) {
		text, n := ReplaceValues(text, map[string]string{"ui.Outgame.Footer.Quest": "Missões"})
		return text, n > 0
	})
	if err != nil || !changed {
		t.Fatalf("changed=%v err=%v", changed, err)
	}
	if out[0] != raw[0] {
		t.Fatalf("marker %x, want %x", out[0], raw[0])
	}
	plain, err := unityasset.Unmask(out, "text)en)ui")
	if err != nil {
		t.Fatal(err)
	}
	b, err := unityasset.ParseBundle(plain)
	if err != nil {
		t.Fatal(err)
	}
	found := false
	for _, file := range b.Files {
		found = found || strings.Contains(string(file), "ui.Outgame.Footer.Quest:Missões")
	}
	if !found {
		t.Fatal("new text not in the rebuilt bundle")
	}
}
