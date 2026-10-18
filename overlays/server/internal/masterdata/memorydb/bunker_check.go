package memorydb

import (
	"fmt"
	"os"

	"github.com/vmihailenco/msgpack/v5"
)

// requiredTables are tables every 3.7.1 master data has, the ones Pod
// Programs' patcher also requires.
var requiredTables = []string{"m_costume", "m_weapon", "m_event_quest_chapter", "m_shop", "m_mom_banner"}

// Check reports whether path is master data the server can load: it decrypts,
// has a table index, every table lies inside the file, and the required
// tables decode. The loaded tables are not touched.
func Check(path string) error {
	encrypted, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("read bin.e: %w", err)
	}
	decrypted, err := decrypt(encrypted)
	if err != nil {
		return fmt.Errorf("decrypt: %w", err)
	}
	toc, blob, err := parseHeader(decrypted)
	if err != nil {
		return fmt.Errorf("parse header: %w", err)
	}
	for name, offLen := range toc {
		if offLen[0] < 0 || offLen[1] < 0 || offLen[0]+offLen[1] > len(blob) {
			return fmt.Errorf("table %q lies outside the file", name)
		}
	}
	for _, name := range requiredTables {
		offLen, ok := toc[name]
		if !ok {
			return fmt.Errorf("table %q is missing", name)
		}
		if _, err := decompressAndUnmarshal[msgpack.RawMessage](blob[offLen[0] : offLen[0]+offLen[1]]); err != nil {
			return fmt.Errorf("table %q: %w", name, err)
		}
	}
	return nil
}
