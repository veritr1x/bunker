package lunarbase

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/store"
)

// A save at the start of chapter 16 (route 2): the head on quest 305's first
// scene (611), with no quests cleared.
func storySave(t *testing.T) string {
	path := filepath.Join(t.TempDir(), "game.db")
	if err := NewStage(path); err != nil {
		t.Fatal(err)
	}
	db, st, err := openDB(path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if _, err := st.UpdateUser(1, func(u *store.UserState) {
		u.Costumes["c1"] = store.CostumeState{UserCostumeUuid: "c1", CostumeId: 10100}
		u.MainQuest.HeadQuestSceneId, u.MainQuest.CurrentQuestSceneId = 611, 611
		u.MainQuest.CurrentMainQuestRouteId, u.MainQuest.MainQuestSeasonId, u.MainQuest.CurrentQuestFlowType = 2, 2, 1
	}); err != nil {
		t.Fatal(err)
	}
	return path
}

func storyMasters(t *testing.T) map[string]string {
	out := map[string]string{}
	for _, env := range []string{"BUNKER_TEST_MASTER", "BUNKER_TEST_MASTER_JP"} {
		if m := os.Getenv(env); m != "" {
			out[env] = m
		}
	}
	if len(out) == 0 {
		t.Skip("BUNKER_TEST_MASTER and BUNKER_TEST_MASTER_JP not set")
	}
	return out
}

func storyRun(t *testing.T, raw string) (int, map[string]any) {
	t.Helper()
	var reply struct {
		OK      bool           `json:"ok"`
		Error   string         `json:"error"`
		Applied int            `json:"applied"`
		Data    map[string]any `json:"data"`
	}
	if err := json.Unmarshal([]byte(Execute([]byte(raw))), &reply); err != nil {
		t.Fatal(err)
	}
	if !reply.OK {
		t.Fatalf("%s: %s", raw, reply.Error)
	}
	return reply.Applied, reply.Data
}

func TestStoryShim(t *testing.T) {
	for env, master := range storyMasters(t) {
		t.Run(env, func(t *testing.T) {
			path := storySave(t)
			base := fmt.Sprintf(`"db_path":%q,"master_data_path":%q,"user_id":1`, path, master)

			_, dry := storyRun(t, `{"action":"story_jump",`+base+`,"story":{"quest_id":317,"season2_route":2,"dry_run":true}}`)
			cleared := dry["cleared"].([]any)
			// Nothing is cleared in this save, so the path runs from quest 1 to 316:
			// season 1 (110), chapter 15 (301) and chapter 16 up to 317 (305-316).
			if len(cleared) != 110+1+12 || cleared[0] != float64(1) || cleared[len(cleared)-1] != float64(316) || dry["dry_run"] != true {
				t.Fatalf("dry run cleared %d quests: %v", len(cleared), cleared)
			}
			if n := countCleared(t, path); n != 0 {
				t.Fatalf("a dry run cleared %d quests", n)
			}

			applied, _ := storyRun(t, `{"action":"story_jump",`+base+`,"story":{"quest_id":317,"season2_route":2}}`)
			if applied != len(cleared) || countCleared(t, path) != len(cleared) {
				t.Fatalf("applied %d, %d cleared in the save, dry run said %d", applied, countCleared(t, path), len(cleared))
			}
			db, err := database.Open(path)
			if err != nil {
				t.Fatal(err)
			}
			defer db.Close()
			var head int
			if err := db.QueryRow("SELECT head_quest_scene_id FROM user_main_quest WHERE user_id = 1").Scan(&head); err != nil {
				t.Fatal(err)
			}
			if head != 706 { // quest 317's first scene
				t.Fatalf("head scene %d after the jump, want 706", head)
			}

			reply := Execute([]byte(`{"action":"story_jump",` + base + `,"story":{"quest_id":306,"season2_route":2}}`))
			if !json.Valid([]byte(reply)) || !strings.Contains(reply, "already at or past") {
				t.Fatalf("a backward jump: %s", reply)
			}
		})
	}
}

func countCleared(t *testing.T, path string) int {
	db, err := database.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	var n int
	if err := db.QueryRow("SELECT count(*) FROM user_quests WHERE user_id = 1 AND quest_state_type = 2").Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}
