package userdata

import (
	"encoding/json"
	"slices"
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// EntityIUserCharacterViewerField has exactly these columns; an unknown one
// (e.g. isViewed) breaks the client.
func TestCharacterViewerFieldColumns(t *testing.T) {
	user := store.SeedUserState(7, "u", 0, model.DefaultPlatform)
	before := store.CloneUserState(*user)
	user.Ext.CharacterViewerFields = map[int32]int64{3: 1000, 1: 500}
	var rows []map[string]any
	if err := json.Unmarshal([]byte(FullClientTableMap(*user)["IUserCharacterViewerField"]), &rows); err != nil {
		t.Fatal(err)
	}
	if len(rows) != 2 || rows[0]["characterViewerFieldId"] != float64(1) || rows[1]["releaseDatetime"] != float64(1000) {
		t.Fatalf("rows %v", rows)
	}
	for _, r := range rows {
		var cols []string
		for k := range r {
			cols = append(cols, k)
		}
		slices.Sort(cols)
		if !slices.Equal(cols, []string{"characterViewerFieldId", "latestVersion", "releaseDatetime", "userId"}) {
			t.Fatalf("columns %v", cols)
		}
	}
	if !slices.Contains(ChangedTables(&before, user), "IUserCharacterViewerField") {
		t.Fatal("change not detected")
	}
}
