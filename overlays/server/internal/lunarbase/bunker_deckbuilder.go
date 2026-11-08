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
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/pvp"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/store/sqlite"
	"lunar-tear/server/migrations"
)

// readData is what a read action found, sent back in the reply's "data"
// (patches/lunar-base-zzz-deckbuilder.patch).
var readData any

func takeReadData() any {
	d := readData
	readData = nil
	return d
}

// runArenaMatching: "arena_matching" answers with the player's current
// matching list (pvp.Opponent), reading the save only.
func runArenaMatching(req *request) (int, error) {
	// While the game's server runs (in this process), use its catalog: loading
	// the master data again would swap the tables under it.
	c := pvp.Current()
	if c == nil {
		if req.MasterDataPath == "" {
			return 0, errors.New("master_data_path required for arena_matching")
		}
		h, err := runtime.NewHolder(req.MasterDataPath)
		if err != nil {
			return 0, err
		}
		c = pvp.CatalogFor(h.Get())
	}
	db, st, err := openDB(req.DBPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	u, err := st.LoadUser(req.UserID)
	if err != nil {
		return 0, err
	}
	ops := c.Opponents(&u, giftNow())
	if ops == nil {
		ops = []pvp.Opponent{}
	}
	readData = ops
	return len(ops), nil
}

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

// rankSpec is one "rank_characters" entry: a character and the rank to raise it to.
type rankSpec struct {
	CharacterID int32 `json:"character_id"`
	Level       int32 `json:"level"`
}

// runRankCharacters: "rank_characters" raises each named character to its rank
// (IUserCharacter.level; the game's top is 10, CharacterLevelBonusAbilityGroup),
// adding the character when the save lacks it. A rank is never lowered.
func runRankCharacters(req *request) (int, error) {
	if len(req.Ranks) == 0 {
		return 0, errors.New("ranks list is empty")
	}
	db, st, err := openDB(req.DBPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	now := time.Now().UnixMilli()
	applied := 0
	_, err = st.UpdateUser(req.UserID, func(u *store.UserState) {
		for _, r := range req.Ranks {
			cur, ok := u.Characters[r.CharacterID]
			if r.Level <= 0 || (ok && cur.Level >= r.Level) {
				continue
			}
			cur.CharacterId, cur.Level, cur.LatestVersion = r.CharacterID, r.Level, now
			u.Characters[r.CharacterID] = cur
			applied++
		}
	})
	if err != nil {
		return 0, fmt.Errorf("rank characters: %w", err)
	}
	return applied, nil
}
