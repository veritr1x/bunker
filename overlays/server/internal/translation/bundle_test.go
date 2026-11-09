package translation

import (
	"bytes"
	"math/rand"
	"os"
	"path/filepath"
	"strings"
	"testing"

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
