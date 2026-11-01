package service

import (
	"os"
	"path/filepath"

	"lunar-tear/server/internal/gametime"
)

// ViewMasterName is the game data the client downloads in the original-dates
// view: the loop's data with no date shift (android_calendar.py VIEW_NAME),
// beside the master data.
const ViewMasterName = "calendar-view.bin.e"

// viewMasterFile is the game data file the client gets: the view copy in the
// original-dates view if it was built, else the master data itself.
func viewMasterFile(masterPath string) string {
	if gametime.ViewOffset() == 0 {
		return masterPath
	}
	view := filepath.Join(filepath.Dir(masterPath), ViewMasterName)
	if _, err := os.Stat(view); err != nil {
		return masterPath
	}
	return view
}

// viewMasterSuffix marks the version of the view copy, so a switch makes the
// client download the other file.
func viewMasterSuffix(masterPath string) string {
	if viewMasterFile(masterPath) != masterPath {
		return "_view"
	}
	return ""
}
