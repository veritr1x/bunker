package service

import (
	"bytes"
	"encoding/binary"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
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

func listBinItem(id, path string, size uint64, md5 string) []byte {
	var e []byte
	e = append(e, protoBytes(3, []byte(path))...)
	e = append(e, protoVarint(4, size)...)
	e = append(e, protoVarint(7, 99)...) // a field the index does not read
	e = append(e, protoBytes(10, []byte(md5))...)
	e = append(e, protoBytes(11, []byte(id))...)
	return protoBytes(1, e)
}

// mapListBin is the map list.bin was indexed into before: object_id → entry, the last entry winning.
func mapListBin(data []byte) map[string]listBinEntry {
	m := map[string]listBinEntry{}
	for i := 0; i < len(data); {
		tag, n := readVarint(data[i:])
		if n == 0 {
			break
		}
		i += n
		if tag&7 == 2 {
			length, vn := readVarint(data[i:])
			if vn == 0 || i+vn+length > len(data) {
				break
			}
			if id, e, ok := parseListBinEntry(data[i+vn : i+vn+length]); ok {
				m[id] = e
			}
			i += vn + length
			continue
		}
		next, ok := skipProtoField(tag&7, data, i)
		if !ok {
			break
		}
		i = next
	}
	return m
}

// writeListBin writes data as revision 0's Android list.bin in a new assets folder. The index
// cache is keyed by revision and platform only, so it is reset around each test.
func writeListBin(t *testing.T, data []byte) string {
	t.Helper()
	ResetOctoCaches()
	t.Cleanup(ResetOctoCaches)
	dir := t.TempDir()
	path := filepath.Join(dir, "assets", "revisions", "0", "android", "list.bin")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
	return dir
}

func checkIndex(t *testing.T, idx *listBinIndex, want map[string]listBinEntry) {
	t.Helper()
	for id, w := range want {
		got, ok := idx.lookup(id)
		if !ok || got != w {
			t.Fatalf("lookup(%q) = %+v, %v; want %+v", id, got, ok, w)
		}
	}
	if n := idx.len(); n != len(want) {
		t.Fatalf("index holds %d entries, want %d", n, len(want))
	}
}

func TestListBinIndexMatchesMap(t *testing.T) {
	var data []byte
	data = append(data, protoBytes(2, []byte("http://resources.example/aaaaaaaaaaaaaaaaaaaaa"))...)
	data = append(data, listBinItem("Abc123", "ui)gacha)ja)banner", 4096, "0123456789abcdef0123456789abcdef")...)
	data = append(data, listBinItem("Zz9", "voice)en)main)line", 300, "fedcba9876543210fedcba9876543210")...)
	data = append(data, protoVarint(5, 12345)...) // a top-level varint between entries
	data = append(data, listBinItem("Abc123", "ui)gacha)en)banner", 8192, "11111111111111111111111111111111")...)
	data = append(data, listBinItem("a-much-longer-object-id", "3d)actor)ch008001", 70000, "22222222222222222222222222222222")...)
	data = append(data, listBinItem("small", "2d)icon", 12, "33333333333333333333333333333333")...) // size < 256 reads as 0
	data = append(data, protoBytes(1, protoBytes(3, []byte("no)object)id")))...)
	data = append(data, listBinItem("id\x00zero", "ui)zero", 512, "44444444444444444444444444444444")...)
	want := mapListBin(data)
	if len(want) != 5 {
		t.Fatalf("test data has %d entries, want 5", len(want))
	}
	idx, ok := loadListBinIndex(writeListBin(t, data), "0", "android")
	if !ok {
		t.Fatal("index not loaded")
	}
	checkIndex(t, idx, want)
	for _, id := range []string{"", "Abc12", "Abc1234", "nope", "id"} {
		if e, ok := idx.lookup(id); ok {
			t.Fatalf("lookup(%q) found %+v", id, e)
		}
	}
}

func TestListBinIndexStopsAtDamage(t *testing.T) {
	data := listBinItem("Abc123", "ui)a", 4096, "0123456789abcdef0123456789abcdef")
	data = append(data, protoTag(1, 2)...)
	data = append(data, 0xff, 0xff, 0x7f) // a length past the end of the file
	want := mapListBin(data)
	idx, ok := loadListBinIndex(writeListBin(t, data), "0", "android")
	if !ok {
		t.Fatal("index not loaded")
	}
	checkIndex(t, idx, want)
}

// TestListBinIndexDump checks the index against the whole 3.7.1 list.bin when
// BUNKER_TEST_LIST_BIN names it.
func TestListBinIndexDump(t *testing.T) {
	path := os.Getenv("BUNKER_TEST_LIST_BIN")
	if path == "" {
		t.Skip("set BUNKER_TEST_LIST_BIN to a dump's revisions/0/list.bin")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	idx, ok := loadListBinIndex(writeListBin(t, data), "0", "android")
	if !ok {
		t.Fatal("index not loaded")
	}
	checkIndex(t, idx, mapListBin(data))
}

func TestServeListBinRewritesURL(t *testing.T) {
	head := protoBytes(2, []byte(resourcesURLOriginal))
	body := bytes.Repeat(listBinItem("Abc123", "ui)a", 4096, "0123456789abcdef0123456789abcdef"), 5000)
	defer func(n int) { listBinChunk = n }(listBinChunk)
	for _, chunk := range []int{64 << 10, 7, len(resourcesURLOriginal)} {
		listBinChunk = chunk
		for _, data := range [][]byte{append(append([]byte{}, head...), body...), append(append([]byte{}, body...), head...), body} {
			dir := t.TempDir()
			path := filepath.Join(dir, "list.bin")
			if err := os.WriteFile(path, data, 0o644); err != nil {
				t.Fatal(err)
			}
			repl := "http://127.0.0.1:8080/" + string(bytes.Repeat([]byte("r"), len(resourcesURLOriginal)-len("http://127.0.0.1:8080/")))
			s := &OctoHTTPServer{ResourcesBaseURL: repl}
			w := httptest.NewRecorder()
			s.serveListBin(w, path)
			want := bytes.Replace(data, []byte(resourcesURLOriginal), []byte(repl), 1)
			if !bytes.Equal(w.Body.Bytes(), want) {
				t.Fatalf("chunk %d: served list.bin differs (%d bytes, want %d)", chunk, w.Body.Len(), len(want))
			}
			if got := w.Header().Get("Content-Length"); got != strconv.Itoa(len(want)) {
				t.Fatalf("chunk %d: Content-Length %q, want %d", chunk, got, len(want))
			}
		}
	}
}
