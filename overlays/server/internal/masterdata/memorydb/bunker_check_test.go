package memorydb

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/vmihailenco/msgpack/v5"
)

// encrypt is decrypt's inverse, for building small master-data files.
func encrypt(t *testing.T, plain []byte) []byte {
	t.Helper()
	key, _ := hex.DecodeString(aesKeyHex)
	iv, _ := hex.DecodeString(aesIVHex)
	block, _ := aes.NewCipher(key)
	pad := aes.BlockSize - len(plain)%aes.BlockSize
	plain = append(plain, bytes.Repeat([]byte{byte(pad)}, pad)...)
	out := make([]byte, len(plain))
	cipher.NewCBCEncrypter(block, iv).CryptBlocks(out, plain)
	return out
}

func write(t *testing.T, data []byte) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "master.bin.e")
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

// masterWith encodes a header naming tables, each an empty plain array.
func masterWith(t *testing.T, names ...string) []byte {
	t.Helper()
	empty, _ := msgpack.Marshal([]any{})
	header := map[string][]int{}
	var blob []byte
	for _, name := range names {
		header[name] = []int{len(blob), len(empty)}
		blob = append(blob, empty...)
	}
	head, err := msgpack.Marshal(header)
	if err != nil {
		t.Fatal(err)
	}
	return encrypt(t, append(head, blob...))
}

func TestCheckAcceptsTheOriginalMasterData(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	if err := Check(master); err != nil {
		t.Fatalf("Check(original) = %v", err)
	}
}

func TestCheckAcceptsAFileWithTheRequiredTables(t *testing.T) {
	if err := Check(write(t, masterWith(t, requiredTables...))); err != nil {
		t.Fatalf("Check = %v", err)
	}
}

func TestCheckRefusesOtherFiles(t *testing.T) {
	zip := append([]byte("PK\x03\x04"), bytes.Repeat([]byte{7}, 4092)...)
	cases := map[string][]byte{
		"empty":           {},
		"zip":             zip,
		"text":            []byte("not master data\n"),
		"wrong key":       bytes.Repeat([]byte{1}, 4096),
		"missing a table": masterWith(t, requiredTables[1:]...),
	}
	for name, data := range cases {
		err := Check(write(t, data))
		if err == nil {
			t.Errorf("%s: Check accepted it", name)
		}
	}
	if err := Check(write(t, masterWith(t, requiredTables[1:]...))); err == nil || !strings.Contains(err.Error(), requiredTables[0]) {
		t.Errorf("missing table error = %v, want it named", err)
	}
}

func TestCheckLeavesTheLoadedTablesAlone(t *testing.T) {
	tables = map[string][]byte{"m_loaded": {1}}
	defer func() { tables = nil }()
	Check(write(t, masterWith(t, requiredTables...)))
	if _, ok := tables["m_loaded"]; !ok || len(tables) != 1 {
		t.Fatalf("tables changed: %v", tables)
	}
}
