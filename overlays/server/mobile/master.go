package mobile

import (
	"log"
	"os"

	"lunar-tear/server/internal/masterdata/memorydb"
)

// maxMasterSize is far above the master data's 7.5 MB; a larger file (the
// resource dump picked by mistake) is refused without reading it.
const maxMasterSize = 64 << 20

// CheckMaster reports whether a picked file can replace the master data:
// name is the name it was picked by, path a copy of it. Returns "" or a
// message for the player. The contents decide, not the name: a browser
// names a second download "20240405123139.bin (1).e".
func CheckMaster(path, name string) string {
	refused := "That file isn't NieR Re[in]carnation master data. Choose 20240404193219.bin.e " +
		"(Global) or 20240405123139.bin.e (Japanese)."
	if info, err := os.Stat(path); err == nil && info.Size() > maxMasterSize {
		log.Printf("[Master] %s refused: too large (%d bytes)", name, info.Size())
		return refused
	}
	if err := memorydb.Check(path); err != nil {
		log.Printf("[Master] %s refused: %v", name, err)
		return refused
	}
	return ""
}
