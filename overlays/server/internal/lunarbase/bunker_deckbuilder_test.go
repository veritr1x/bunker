package lunarbase

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/internal/database"
)

// arena_matching answers with the matching list and leaves the save as it was.
// Needs real game data (BUNKER_TEST_MASTER); skipped without it.
func TestArenaMatchingReadsOnly(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	path := filepath.Join(t.TempDir(), "game.db")
	if err := NewStage(path); err != nil {
		t.Fatal(err)
	}
	stat := func() string {
		b, _ := os.ReadFile(path)
		return string(b)
	}
	before := stat()
	raw, _ := json.Marshal(map[string]any{"action": "arena_matching", "db_path": path, "user_id": 1, "master_data_path": master})
	out := Execute(raw)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("arena_matching: %s", out)
	}
	if stat() != before {
		t.Fatal("arena_matching wrote to the save")
	}
}

// A deck of owned pieces needs no stage, and a missing stage is never created.
func TestDeckWriteDoesNotCreateAStage(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	dir := t.TempDir()
	path, stage := filepath.Join(dir, "game.db"), filepath.Join(dir, "deckbuilder", "stage.db")
	if err := NewStage(path); err != nil {
		t.Fatal(err)
	}
	deck := json.RawMessage(`{"slots":[{"deck_type":2,"number":5}],"characters":[{"costume":{"uuid":"none","source":"stage"}}]}`)
	raw, _ := json.Marshal(map[string]any{"action": "deck_write", "db_path": path, "user_id": 1, "master_data_path": master, "stage_path": stage, "deck": deck})
	out := Execute(raw)
	if !strings.Contains(out, "stage is not ready") {
		t.Fatalf("deck_write without a stage: %s", out)
	}
	if _, err := os.Stat(stage); !os.IsNotExist(err) {
		t.Fatal("a missing stage was created")
	}
}

// Deck Builder's staging save starts empty with player 1, so the server's own
// grant and upgrade actions can build fully raised pieces on it.
func TestNewStageHasPlayerOne(t *testing.T) {
	path := filepath.Join(t.TempDir(), "deckbuilder", "stage.db")
	if err := NewStage(path); err != nil {
		t.Fatal(err)
	}
	count := func() (int, int) {
		db, err := database.Open(path)
		if err != nil {
			t.Fatal(err)
		}
		defer db.Close()
		var one, all int
		if err := db.QueryRow("SELECT COUNT(*) FROM users WHERE user_id = 1").Scan(&one); err != nil {
			t.Fatal(err)
		}
		if err := db.QueryRow("SELECT COUNT(*) FROM users").Scan(&all); err != nil {
			t.Fatal(err)
		}
		return one, all
	}
	if one, all := count(); one != 1 || all != 1 {
		t.Fatalf("player 1 rows %d, players %d", one, all)
	}
	// A second call starts over rather than adding a player.
	if err := NewStage(path); err != nil {
		t.Fatal(err)
	}
	if one, all := count(); one != 1 || all != 1 {
		t.Fatalf("after a reset: player 1 rows %d, players %d", one, all)
	}
}
