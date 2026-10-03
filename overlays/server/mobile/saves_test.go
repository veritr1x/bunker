package mobile

import (
	"archive/zip"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/migrations"
)

const testKey = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"

// newSaves writes a saves folder with one player, as the server would. The
// uuid is the game's ID on that device; marker tells the players apart.
func newSaves(t *testing.T, dir, uuid string, marker int) {
	t.Helper()
	os.MkdirAll(dir, 0700)
	db, e := database.Open(filepath.Join(dir, "game.db"))
	if e != nil {
		t.Fatal(e)
	}
	if e = migrations.Up(context.Background(), db); e != nil {
		t.Fatal(e)
	}
	if _, e = db.Exec("INSERT INTO users (user_id, uuid, player_id) VALUES (1, ?, ?)", uuid, marker); e != nil {
		t.Fatal(e)
	}
	database.Checkpoint(db)
	db.Close()
	auth, e := database.Open(filepath.Join(dir, "auth.db"))
	if e != nil {
		t.Fatal(e)
	}
	auth.Exec("CREATE TABLE accounts (name TEXT)")
	database.Checkpoint(auth)
	auth.Close()
	for _, suffix := range []string{"-wal", "-shm"} {
		os.Remove(filepath.Join(dir, "game.db"+suffix))
		os.Remove(filepath.Join(dir, "auth.db"+suffix))
	}
	os.WriteFile(filepath.Join(dir, "auth.key"), []byte(testKey), 0600)
}

// zipSaves packs files from dir under a folder, like the iOS export does.
func zipSaves(t *testing.T, dir, target string, names ...string) {
	t.Helper()
	f, _ := os.Create(target)
	w := zip.NewWriter(f)
	for _, name := range names {
		data, e := os.ReadFile(filepath.Join(dir, name))
		if e != nil {
			t.Fatal(e)
		}
		part, _ := w.Create("lunar-tear-saves-20261003/" + name)
		part.Write(data)
	}
	part, _ := w.Create("lunar-tear-saves-20261003/README.txt")
	part.Write([]byte("readme"))
	w.Close()
	f.Close()
}

// player returns the save's only player as "uuid/marker".
func player(t *testing.T, dir string) string {
	t.Helper()
	db, e := database.Open(filepath.Join(dir, "game.db"))
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	var uuid string
	var marker int
	if e = db.QueryRow("SELECT uuid, player_id FROM users").Scan(&uuid, &marker); e != nil {
		t.Fatal(e)
	}
	return fmt.Sprintf("%s/%d", uuid, marker)
}

func TestImportSavesFromExport(t *testing.T) {
	Stop()
	root := t.TempDir()
	saves, backup := filepath.Join(root, "saves"), filepath.Join(root, "backup")
	newSaves(t, saves, "this-device", 1)
	os.WriteFile(filepath.Join(saves, "game.db-wal"), []byte("stale"), 0600)
	newSaves(t, backup, "other-device", 2)
	archive := filepath.Join(root, "backup.zip")
	zipSaves(t, backup, archive, "game.db", "auth.db", "auth.key")
	if e := ImportSaves(saves, archive); e != "" {
		t.Fatal(e)
	}
	// The imported player now answers to this device's game ID.
	if got := player(t, saves); got != "this-device/2" {
		t.Fatalf("player %q", got)
	}
	if got := player(t, saves+".before-import"); got != "this-device/1" {
		t.Fatalf("previous save %q", got)
	}
	if _, e := os.Stat(saves + ".importing"); !os.IsNotExist(e) {
		t.Fatal("staging folder left behind")
	}
}

func TestImportBareGameKeepsSignIn(t *testing.T) {
	Stop()
	root := t.TempDir()
	saves, backup := filepath.Join(root, "saves"), filepath.Join(root, "backup")
	newSaves(t, saves, "this-device", 1)
	newSaves(t, backup, "this-device", 2) // A backup from this same install.
	os.WriteFile(filepath.Join(saves, "auth.key"), []byte(strings.Repeat("ab", 32)), 0600)
	if e := ImportSaves(saves, filepath.Join(backup, "game.db")); e != "" {
		t.Fatal(e)
	}
	if got := player(t, saves); got != "this-device/2" {
		t.Fatalf("player %q", got)
	}
	if key, _ := os.ReadFile(filepath.Join(saves, "auth.key")); string(key) != strings.Repeat("ab", 32) {
		t.Fatal("sign-in key was not kept")
	}
}

func TestImportSavesRejectsBadBackups(t *testing.T) {
	Stop()
	root := t.TempDir()
	saves, good := filepath.Join(root, "saves"), filepath.Join(root, "good")
	newSaves(t, saves, "this-device", 1)
	newSaves(t, good, "other-device", 2)
	empty := filepath.Join(root, "empty")
	os.MkdirAll(empty, 0700)
	db, _ := database.Open(filepath.Join(empty, "game.db"))
	migrations.Up(context.Background(), db)
	database.Checkpoint(db)
	db.Close()
	os.WriteFile(filepath.Join(root, "notes.txt"), []byte("not a save"), 0600)
	os.WriteFile(filepath.Join(root, "broken.db"), []byte("SQLite format 3\x00broken"), 0600)
	zipSaves(t, good, filepath.Join(root, "no-game.zip"), "auth.db", "auth.key")
	zipSaves(t, good, filepath.Join(root, "half-auth.zip"), "game.db", "auth.db")
	zipSaves(t, empty, filepath.Join(root, "no-player.zip"), "game.db")
	os.WriteFile(filepath.Join(good, "auth.key"), []byte("short"), 0600)
	zipSaves(t, good, filepath.Join(root, "bad-key.zip"), "game.db", "auth.db", "auth.key")
	for name, want := range map[string]string{
		"notes.txt": "Choose a save backup", "broken.db": "cannot be", "no-game.zip": "no game.db",
		"half-auth.zip": "together", "no-player.zip": "no player", "bad-key.zip": "auth.key",
	} {
		e := ImportSaves(saves, filepath.Join(root, name))
		if !strings.Contains(e, want) {
			t.Errorf("%s: got %q, want %q", name, e, want)
		}
		if got := player(t, saves); got != "this-device/1" {
			t.Fatalf("%s replaced the save", name)
		}
	}
	if _, e := os.Stat(saves + ".importing"); !os.IsNotExist(e) {
		t.Fatal("staging folder left behind")
	}
}

func TestImportSavesNeedsThisDevicesPlayer(t *testing.T) {
	Stop()
	root := t.TempDir()
	saves, backup := filepath.Join(root, "saves"), filepath.Join(root, "backup")
	os.MkdirAll(saves, 0700)
	newSaves(t, backup, "other-device", 2)
	e := ImportSaves(saves, filepath.Join(backup, "game.db"))
	if !strings.Contains(e, "Open the game once") {
		t.Fatalf("got %q", e)
	}
	if entries, _ := os.ReadDir(saves); len(entries) != 0 {
		t.Fatal("saves changed")
	}
}
