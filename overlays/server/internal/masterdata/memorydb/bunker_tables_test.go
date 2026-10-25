package memorydb

import (
	"bytes"
	"fmt"
	"os"
	"testing"

	"github.com/vmihailenco/msgpack/v5"
)

// masterOf encodes tables of the given contents, back to back after the header.
func masterOf(t *testing.T, contents map[string][]byte, order []string) []byte {
	t.Helper()
	toc := map[string][2]int{}
	var blob []byte
	for _, name := range order {
		toc[name] = [2]int{len(blob), len(contents[name])}
		blob = append(blob, contents[name]...)
	}
	header, err := msgpack.Marshal(toc)
	if err != nil {
		t.Fatal(err)
	}
	return append(header, blob...)
}

func checkTables(t *testing.T, want map[string][]byte) {
	t.Helper()
	if TableCount() != len(want) {
		t.Fatalf("TableCount() = %d, want %d", TableCount(), len(want))
	}
	for name, w := range want {
		got, ok := TableBytes(name)
		if !ok || !bytes.Equal(got, w) {
			t.Fatalf("TableBytes(%q) = %d bytes, %v; want %d bytes", name, len(got), ok, len(w))
		}
	}
	if _, ok := TableBytes("m_missing"); ok {
		t.Fatal("TableBytes found a table the file does not have")
	}
}

func TestTablesReadFromFile(t *testing.T) {
	contents := map[string][]byte{}
	var order []string
	for i, n := range []int{0, 1, 15, 16, 17, 31, 33, 100, 4096, 5} {
		name := fmt.Sprintf("m_table_%d", i)
		contents[name] = bytes.Repeat([]byte{byte('a' + i)}, n)
		order = append(order, name)
	}
	path := write(t, encrypt(t, masterOf(t, contents, order)))
	if err := Init(path); err != nil {
		t.Fatal(err)
	}
	checkTables(t, contents)

	// The launcher and the patcher replace master data by renaming a new file
	// over it; until the next Init the tables are the loaded file's.
	other := write(t, encrypt(t, masterOf(t, map[string][]byte{"m_other": []byte("x")}, []string{"m_other"})))
	if err := os.Rename(other, path); err != nil {
		t.Fatal(err)
	}
	checkTables(t, contents)
	if err := Init(path); err != nil {
		t.Fatal(err)
	}
	checkTables(t, map[string][]byte{"m_other": []byte("x")})
}

func TestTablesRefuseBadFile(t *testing.T) {
	path := write(t, encrypt(t, append(mustMarshal(t, map[string][2]int{"m_far": {10, 10}}), 1, 2, 3)))
	if err := Init(path); err == nil {
		t.Fatal("Init accepted a table past the end of the file")
	}
}

func mustMarshal(t *testing.T, v any) []byte {
	t.Helper()
	b, err := msgpack.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

// TestTablesMatchMaster reads every table of the real master data both ways, when the build names it.
func TestTablesMatchMaster(t *testing.T) {
	path := os.Getenv("BUNKER_TEST_MASTER")
	if path == "" {
		t.Skip("set BUNKER_TEST_MASTER to a 20240404193219.bin.e")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	plain, err := decrypt(raw)
	if err != nil {
		t.Fatal(err)
	}
	toc, blob, err := parseHeader(plain)
	if err != nil {
		t.Fatal(err)
	}
	want := map[string][]byte{}
	for name, offLen := range toc {
		want[name] = blob[offLen[0] : offLen[0]+offLen[1]]
	}
	if err := Init(path); err != nil {
		t.Fatal(err)
	}
	checkTables(t, want)
	if _, err := ReadTable[msgpack.RawMessage]("m_costume"); err != nil {
		t.Fatal(err)
	}
}
