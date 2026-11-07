package lunarbase

// Pod Programs › Deck Builder.
//
// Fully raised pieces are built by the server's own actions (the grants,
// upgrade_all_*, exalt_characters, release_panels, fill_karma_slots and the
// memoir grants Upgrade Manager uses) on a staging save, never on the
// player's: NewStage makes that save. Deck Builder reads the result to show
// exact Force, and copies only what the player picks into their save.

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store/sqlite"
	"lunar-tear/server/migrations"
)

// NewStage creates an empty save at path holding only player 1, replacing
// any save already there.
func NewStage(path string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	for _, suffix := range []string{"", "-wal", "-shm"} {
		if err := os.Remove(path + suffix); err != nil && !os.IsNotExist(err) {
			return err
		}
	}
	db, err := database.Open(path)
	if err != nil {
		return err
	}
	defer db.Close()
	if err := migrations.Up(context.Background(), db); err != nil {
		return fmt.Errorf("stage schema: %w", err)
	}
	id, err := sqlite.New(db, nil).CreateUser("deckbuilder-stage", model.DefaultPlatform)
	if err != nil {
		return fmt.Errorf("stage player: %w", err)
	}
	if id != 1 {
		return fmt.Errorf("stage player is %d, not 1", id)
	}
	database.Checkpoint(db)
	return nil
}
