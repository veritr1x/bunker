package lunarbase

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"

	"lunar-tear/server/internal/store"
)

func arenaPvp(t *testing.T, path string) store.PvpState {
	t.Helper()
	db, st, err := openDB(path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	u, err := st.LoadUser(1)
	if err != nil {
		t.Fatal(err)
	}
	return u.Ext.Pvp
}

func arenaReply(t *testing.T, raw string) (bool, string) {
	t.Helper()
	var reply struct {
		OK    bool   `json:"ok"`
		Error string `json:"error"`
	}
	if err := json.Unmarshal([]byte(Execute([]byte(raw))), &reply); err != nil {
		t.Fatal(err)
	}
	return reply.OK, reply.Error
}

// Setting points needs an open season: the patched game data (Bunker's
// content patcher keeps every season open), as the game and server use it.
func TestArenaPointsShim(t *testing.T) {
	master := os.Getenv("LUNAR_TEST_MASTER")
	if master == "" {
		t.Skip("LUNAR_TEST_MASTER not set")
	}
	path := storySave(t)
	base := fmt.Sprintf(`"db_path":%q,"master_data_path":%q,"user_id":1`, path, master)

	applied, data := storyRun(t, `{"action":"set_arena_points",`+base+`,"arena_points":52000}`)
	if applied != 1 || data["point"] != float64(52000) || data["rank"] != float64(1) {
		t.Fatalf("applied %d data %v", applied, data)
	}
	if p := arenaPvp(t, path); p.Point != 52000 || p.SeasonId == 0 {
		t.Fatalf("saved point %d season %d", p.Point, p.SeasonId)
	}

	for _, tc := range []struct{ raw, want string }{
		{`{"action":"set_arena_points",` + base + `,"arena_points":52001}`, "arena points must be 0–52000"},
		{`{"action":"set_arena_points",` + base + `}`, "arena_points required"},
	} {
		if ok, msg := arenaReply(t, tc.raw); ok || msg != tc.want {
			t.Fatalf("%s: ok %v error %q, want %q", tc.raw, ok, msg, tc.want)
		}
	}
	if p := arenaPvp(t, path); p.Point != 52000 {
		t.Fatalf("a refused edit changed the points to %d", p.Point)
	}
}

// The original game data has every season ended: the edit is refused and
// the save keeps its Arena state.
func TestArenaPointsNoSeason(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	path := storySave(t)
	before := arenaPvp(t, path)
	ok, msg := arenaReply(t, fmt.Sprintf(`{"action":"set_arena_points","db_path":%q,"master_data_path":%q,"user_id":1,"arena_points":100}`, path, master))
	if ok || !strings.Contains(msg, "no Arena season is open") {
		t.Fatalf("ok %v error %q, want no Arena season is open", ok, msg)
	}
	if after := arenaPvp(t, path); after.Point != before.Point || after.SeasonId != before.SeasonId {
		t.Fatalf("the save changed: %+v", after)
	}
}
