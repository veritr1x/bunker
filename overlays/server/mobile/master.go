package mobile

import (
	"log"
	"strings"

	"lunar-tear/server/internal/masterdata/memorydb"
)

// CheckMaster reports whether a picked file can replace the master data:
// name is the name it was picked by, path a copy of it. Returns "" or a
// message for the player.
func CheckMaster(path, name string) string {
	if !strings.HasSuffix(strings.ToLower(name), ".bin.e") {
		return "Choose the 20240404193219.bin.e master-data file."
	}
	if err := memorydb.Check(path); err != nil {
		log.Printf("[Master] %s refused: %v", name, err)
		return "That file isn't NieR Re[in]carnation master data. Choose the 20240404193219.bin.e file."
	}
	return ""
}
