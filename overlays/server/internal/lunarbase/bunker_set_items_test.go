package lunarbase

import (
	"fmt"
	"strings"
	"testing"

	"lunar-tear/server/internal/store"
)

func setItemsUser(t *testing.T, path string) store.UserState {
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
	return u
}

// Pod Programs › Item Editor › Set: a stackable's count becomes the amount
// given, up or down, gems included.
func TestSetPossessionBatch(t *testing.T) {
	path := storySave(t)
	base := fmt.Sprintf(`"db_path":%q,"user_id":1`, path)
	storyRun(t, `{"action":"grant_batch",`+base+`,"grants":[{"possession_type":6,"possession_id":43,"count":4590},{"possession_type":11,"possession_id":0,"count":500}]}`)

	applied, _ := storyRun(t, `{"action":"set_possession_batch",`+base+`,"grants":[`+
		`{"possession_type":6,"possession_id":43,"count":12},{"possession_type":5,"possession_id":100002,"count":7},`+
		`{"possession_type":11,"possession_id":0,"count":0},{"possession_type":12,"possession_id":0,"count":300},`+
		`{"possession_type":13,"possession_id":9,"count":1}]}`)
	if applied != 5 {
		t.Fatalf("applied %d", applied)
	}
	u := setItemsUser(t, path)
	if u.ConsumableItems[43] != 12 || u.Materials[100002] != 7 || u.Gem.PaidGem != 0 || u.Gem.FreeGem != 300 || u.ImportantItems[9] != 1 {
		t.Fatalf("consumable %d material %d paid %d free %d important %d",
			u.ConsumableItems[43], u.Materials[100002], u.Gem.PaidGem, u.Gem.FreeGem, u.ImportantItems[9])
	}

	for _, tc := range []struct{ raw, want string }{
		{`{"action":"set_possession_batch",` + base + `,"grants":[]}`, "grants list is empty"},
		{`{"action":"set_possession_batch",` + base + `,"grants":[{"possession_type":6,"possession_id":43,"count":-1}]}`, "count must not be negative"},
		{`{"action":"set_possession_batch",` + base + `,"grants":[{"possession_type":1,"possession_id":43,"count":1}]}`, "unsupported stackable item type"},
		{`{"action":"set_possession_batch",` + base + `,"grants":[{"possession_type":11,"possession_id":0,"count":2000000000},{"possession_type":12,"possession_id":0,"count":2000000000}]}`, "the game's inventory limit"},
	} {
		ok, msg := arenaReply(t, tc.raw)
		if ok || msg == "" || !strings.Contains(msg, tc.want) {
			t.Fatalf("%s: ok %v error %q, want %q", tc.raw, ok, msg, tc.want)
		}
	}
	if u := setItemsUser(t, path); u.ConsumableItems[43] != 12 || u.Gem.FreeGem != 300 {
		t.Fatalf("a refused batch changed the save: %d %d", u.ConsumableItems[43], u.Gem.FreeGem)
	}
}
