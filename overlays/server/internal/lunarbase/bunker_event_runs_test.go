package lunarbase

import (
	"os"
	"testing"
	"time"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// End to end on game data the Original calendar built (BUNKER_TEST_LOOP_MASTER:
// android_calendar.build_master from the final game data): the Automata
// event's first run (chapter 510) drops its own Automata Medal (25), its
// second (chapter 510 + COPY_STEP) medal 46 and its last (510 + 2 * COPY_STEP)
// the final game data's Bronze Automata Medal (149).
func TestEachAutomataRunDropsItsOwnMedal(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_LOOP_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_LOOP_MASTER not set")
	}
	h, _, err := storyHandler(master)
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range []struct{ chapter, medal int32 }{{510, 25}, {510 + 10_000_000, 46}, {510 + 20_000_000, 149}} {
		u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
		now := time.Now().UnixMilli()
		h.HandleEventQuestStart(u, c.chapter, 200271, false, 1, now)
		h.HandleEventQuestFinish(u, c.chapter, 200271, false, false, now)
		got := map[int32]int32{}
		for _, id := range []int32{25, 46, 149} {
			got[id] = u.ConsumableItems[id]
		}
		if got[c.medal] == 0 {
			t.Errorf("chapter %d: medals %v, want medal %d", c.chapter, got, c.medal)
		}
		for id, n := range got {
			if id != c.medal && n != 0 {
				t.Errorf("chapter %d: got %d of medal %d, another run's", c.chapter, n, id)
			}
		}
	}
}
