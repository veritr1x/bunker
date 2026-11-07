package lunarbase

import (
	"path/filepath"
	"testing"

	"lunar-tear/server/internal/database"
)

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
