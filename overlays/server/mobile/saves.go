package mobile

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"strings"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/migrations"
)

// Largest accepted size for each file in a save backup.
var saveLimits = map[string]int64{"game.db": 2 << 30, "auth.db": 256 << 20, "auth.key": 1 << 10}

// ImportSaves replaces the saves in dataRoot with a backup from Export save
// backup (a ZIP of game.db, auth.db and auth.key, from Android or iOS) or with
// a bare game.db. Everything is checked in a staging folder first, and the
// current saves are kept in <dataRoot>.before-import. The server must be
// stopped. Returns "" or an error for the player.
//
// The game finds its player by an ID it creates on each device and install.
// The imported player takes over this device's ID, so the game loads it.
func ImportSaves(dataRoot, source string) string {
	lifecycle.Lock()
	defer lifecycle.Unlock()
	if active != nil {
		return "Stop the server before importing a save"
	}
	if e := importSaves(dataRoot, source); e != nil {
		return e.Error()
	}
	return ""
}

func importSaves(dataRoot, source string) error {
	stage := dataRoot + ".importing"
	os.RemoveAll(stage)
	if e := os.MkdirAll(stage, 0700); e != nil {
		return e
	}
	installed := false
	defer func() {
		if !installed {
			os.RemoveAll(stage)
		}
	}()
	found, e := extractSaves(source, stage)
	if e != nil {
		return e
	}
	if !found["game.db"] {
		return errors.New("This backup has no game.db")
	}
	if found["auth.db"] != found["auth.key"] {
		return errors.New("This backup has only one of auth.db and auth.key. They must be imported together")
	}
	if !found["auth.db"] {
		// A bare game.db keeps this device's sign-in files.
		for _, name := range []string{"auth.db", "auth.key"} {
			if e := copyFile(filepath.Join(dataRoot, name), filepath.Join(stage, name)); e != nil && !os.IsNotExist(e) {
				return e
			}
		}
	}
	if e := checkSave(filepath.Join(stage, "game.db"), true); e != nil {
		return fmt.Errorf("game.db %w", e)
	}
	device, e := devicePlayer(filepath.Join(dataRoot, "game.db"))
	if e != nil {
		return e
	}
	if e := adoptDevice(filepath.Join(stage, "game.db"), device); e != nil {
		return e
	}
	if _, e := os.Stat(filepath.Join(stage, "auth.db")); e == nil {
		if e := checkSave(filepath.Join(stage, "auth.db"), false); e != nil {
			return fmt.Errorf("auth.db %w", e)
		}
	}
	if b, e := os.ReadFile(filepath.Join(stage, "auth.key")); e == nil {
		if key, e := hex.DecodeString(strings.TrimSpace(string(b))); e != nil || len(key) != 32 {
			return errors.New("auth.key is not a valid sign-in key")
		}
	}
	previous := dataRoot + ".before-import"
	os.RemoveAll(previous)
	if _, e := os.Stat(dataRoot); e == nil {
		if e := os.Rename(dataRoot, previous); e != nil {
			return e
		}
	}
	if e := os.Rename(stage, dataRoot); e != nil {
		os.Rename(previous, dataRoot)
		return e
	}
	installed = true
	return nil
}

// extractSaves copies game.db, auth.db and auth.key from a ZIP (at any depth,
// as both platforms' exports differ) or a bare game.db into stage.
func extractSaves(source, stage string) (map[string]bool, error) {
	found := map[string]bool{}
	f, e := os.Open(source)
	if e != nil {
		return nil, e
	}
	header := make([]byte, 16)
	n, _ := io.ReadFull(f, header)
	f.Close()
	if bytes.Equal(header[:n], []byte("SQLite format 3\x00")) {
		found["game.db"] = true
		return found, copyFile(source, filepath.Join(stage, "game.db"))
	}
	r, e := zip.OpenReader(source)
	if e != nil {
		return nil, errors.New("Choose a save backup (.zip) made by Export save backup, or a game.db file")
	}
	defer r.Close()
	for _, entry := range r.File {
		name := path.Base(entry.Name)
		limit, wanted := saveLimits[name]
		if entry.FileInfo().IsDir() || !wanted || strings.HasPrefix(entry.Name, "__MACOSX/") {
			continue
		}
		if found[name] {
			return nil, fmt.Errorf("This backup has more than one %s", name)
		}
		if entry.UncompressedSize64 > uint64(limit) {
			return nil, fmt.Errorf("%s in this backup is too large", name)
		}
		in, e := entry.Open()
		if e != nil {
			return nil, e
		}
		out, e := os.OpenFile(filepath.Join(stage, name), os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if e != nil {
			in.Close()
			return nil, e
		}
		written, e := io.Copy(out, io.LimitReader(in, limit+1))
		in.Close()
		if e == nil {
			e = out.Sync()
		}
		if c := out.Close(); e == nil {
			e = c
		}
		if e != nil {
			return nil, fmt.Errorf("Cannot read %s from the backup: %w", name, e)
		}
		if written > limit {
			return nil, fmt.Errorf("%s in this backup is too large", name)
		}
		found[name] = true
	}
	return found, nil
}

// devicePlayer returns the game's ID on this device: that of the most recently
// started player in the current save.
func devicePlayer(game string) (string, error) {
	const first = "Open the game once on this device so it creates its player, then import the backup"
	if _, e := os.Stat(game); e != nil {
		return "", errors.New(first)
	}
	db, e := database.Open(game)
	if e != nil {
		return "", fmt.Errorf("Cannot read the current save: %w", e)
	}
	defer db.Close()
	var uuid string
	if e = db.QueryRow("SELECT uuid FROM users ORDER BY game_start_datetime DESC, user_id DESC LIMIT 1").Scan(&uuid); e != nil {
		return "", errors.New(first)
	}
	return uuid, nil
}

// adoptDevice gives the backup's most recently started player this device's
// ID, unless the backup already has it (a backup from this same install).
func adoptDevice(game, device string) error {
	db, e := database.Open(game)
	if e != nil {
		return e
	}
	defer func() {
		database.Checkpoint(db)
		db.Close()
		os.Remove(game + "-wal")
		os.Remove(game + "-shm")
	}()
	var mine int
	if e = db.QueryRow("SELECT COUNT(*) FROM users WHERE uuid = ?", device).Scan(&mine); e != nil || mine > 0 {
		return e
	}
	var player int64
	if e = db.QueryRow("SELECT user_id FROM users ORDER BY game_start_datetime DESC, user_id DESC LIMIT 1").Scan(&player); e != nil {
		return e
	}
	if _, e = db.Exec("UPDATE users SET uuid = ? WHERE user_id = ?", device, player); e != nil {
		return fmt.Errorf("Cannot move the player to this device: %w", e)
	}
	// Sessions belong to the other device's ID; the game signs in again.
	_, e = db.Exec("DELETE FROM sessions")
	return e
}

// checkSave opens a staged database the way the server does, bringing an older
// game save up to date, and checks it is complete.
func checkSave(p string, game bool) error {
	db, e := database.Open(p)
	if e != nil {
		return fmt.Errorf("cannot be opened: %w", e)
	}
	defer func() {
		database.Checkpoint(db)
		db.Close()
		os.Remove(p + "-wal")
		os.Remove(p + "-shm")
	}()
	if game {
		if e = migrations.Up(context.Background(), db); e != nil {
			return fmt.Errorf("cannot be updated: %w", e)
		}
	}
	var result string
	if e = db.QueryRow("PRAGMA integrity_check").Scan(&result); e != nil || result != "ok" {
		return errors.New("is damaged and failed its integrity check")
	}
	if game {
		var players int
		if e = db.QueryRow("SELECT COUNT(*) FROM users").Scan(&players); e != nil || players == 0 {
			return errors.New("has no player in it")
		}
	}
	return nil
}

func copyFile(from, to string) error {
	in, e := os.Open(from)
	if e != nil {
		return e
	}
	defer in.Close()
	out, e := os.OpenFile(to, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0600)
	if e != nil {
		return e
	}
	if _, e = io.Copy(out, in); e == nil {
		e = out.Sync()
	}
	if c := out.Close(); e == nil {
		e = c
	}
	return e
}
