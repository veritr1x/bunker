package translation

import (
	"bytes"
	"encoding/binary"
	"os"
	"path/filepath"
	"testing"
)

func protoTag(field, wire int) []byte { return binary.AppendUvarint(nil, uint64(field<<3|wire)) }

func protoBytes(field int, v []byte) []byte {
	b := append(protoTag(field, 2), binary.AppendUvarint(nil, uint64(len(v)))...)
	return append(b, v...)
}

func protoVarint(field int, v uint64) []byte {
	return append(protoTag(field, 0), binary.AppendUvarint(nil, v)...)
}

func listItem(id, path string, size, crc uint64, md5 string) []byte {
	var e []byte
	e = append(e, protoVarint(1, 7)...)
	e = append(e, protoBytes(3, []byte(path))...)
	e = append(e, protoVarint(4, size)...)
	e = append(e, protoVarint(5, crc)...)
	e = append(e, protoVarint(9, 2)...)
	e = append(e, protoBytes(10, []byte(md5))...)
	e = append(e, protoBytes(11, []byte(id))...)
	e = append(e, protoVarint(12, 1626410850428981)...)
	return protoBytes(2, e)
}

func sampleList() ([]byte, []byte) {
	other := listItem("i9kb1A", "text)en)gift", 1692, 3054123202, "0695e09572b065662adf95420cc285f9")
	var b []byte
	b = append(b, protoVarint(1, 817)...)
	b = append(b, listItem("vqZsA7", "text)en)ui", 25733, 3069911305, "dc1c7484dae87ae3095f9a70c6c3d63b")...)
	b = append(b, other...)
	b = append(b, protoBytes(4, []byte("\x08\x01\x1a\x07tag.txt"))...)
	return b, other
}

func TestParseList(t *testing.T) {
	data, _ := sampleList()
	revision, entries, err := ParseList(data)
	if err != nil || revision != 817 || len(entries) != 2 {
		t.Fatalf("revision %d, %d entries, %v", revision, len(entries), err)
	}
	want := Entry{ObjectID: "vqZsA7", Path: "text)en)ui", Size: 25733, CRC: 3069911305, MD5: "dc1c7484dae87ae3095f9a70c6c3d63b"}
	if entries[0] != want {
		t.Fatalf("got %+v", entries[0])
	}
}

func TestPatchListChangesOnlyNamedEntries(t *testing.T) {
	data, other := sampleList()
	changed := Entry{ObjectID: "vqZsA7", Path: "text)en)ui", Size: 300, CRC: 7, MD5: "abababababababababababababababab"}
	out, err := PatchList(data, 817, map[string]Entry{"vqZsA7": changed}, nil)
	if err != nil {
		t.Fatal(err)
	}
	_, entries, err := ParseList(out)
	if err != nil || entries[0] != changed {
		t.Fatalf("got %+v, %v", entries, err)
	}
	if !bytes.Contains(out, other) || !bytes.HasSuffix(out, protoBytes(4, []byte("\x08\x01\x1a\x07tag.txt"))) {
		t.Fatal("other fields changed")
	}
	if !bytes.Contains(out, protoVarint(12, 1626410850428981)) {
		t.Fatal("unchanged entry field lost")
	}
}

func TestPatchListRevisionOnly(t *testing.T) {
	data, _ := sampleList()
	out, err := PatchList(data, 1818, nil, nil)
	if err != nil {
		t.Fatal(err)
	}
	want := append(protoVarint(1, 1818), data[len(protoVarint(1, 817)):]...)
	if !bytes.Equal(out, want) {
		t.Fatal("more than the revision changed")
	}
}

func TestPatchListUnknownID(t *testing.T) {
	data, _ := sampleList()
	if _, err := PatchList(data, 818, map[string]Entry{"nope00": {ObjectID: "nope00"}}, nil); err == nil {
		t.Fatal("no error")
	}
}

// Patching the real 26 MB list for a game start: one translated entry.
func BenchmarkPatchRealList(b *testing.B) {
	dump := os.Getenv("ARCHIVE_DUMP")
	if dump == "" {
		b.Skip("set ARCHIVE_DUMP to an extracted revisions/0")
	}
	data, err := os.ReadFile(filepath.Join(dump, "list.bin"))
	if err != nil {
		b.Fatal(err)
	}
	changes := map[string]Entry{uiID: {ObjectID: uiID, Size: 300, CRC: 7, MD5: "abababababababababababababababab"}}
	b.ReportAllocs()
	for b.Loop() {
		if _, err := PatchList(data, 1817, changes, nil); err != nil {
			b.Fatal(err)
		}
	}
}

func TestRealList(t *testing.T) {
	data, err := os.ReadFile(filepath.Join(dumpRevision(t), "list.bin"))
	if err != nil {
		t.Fatal(err)
	}
	revision, entries, err := ParseList(data)
	if err != nil || revision != 817 || len(entries) != 200801 {
		t.Fatalf("revision %d, %d entries, %v", revision, len(entries), err)
	}
	for _, e := range entries {
		if e.Path == "text)en)gift" {
			if e.CRC != 3054123202 || e.MD5 != "0695e09572b065662adf95420cc285f9" {
				t.Fatalf("%+v", e)
			}
			return
		}
	}
	t.Fatal("text)en)gift not found")
}
