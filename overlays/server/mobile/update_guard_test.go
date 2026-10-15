package mobile

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/migrations"
)

func openSave(t *testing.T, dir string) *sql.DB {
	t.Helper()
	db, err := database.Open(filepath.Join(dir, "game.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func updateSnapshots(dir string) []string {
	m, _ := filepath.Glob(filepath.Join(dir, "backup_*_update.db"))
	return m
}

func savedVersion(t *testing.T, dir string) string {
	b, _ := os.ReadFile(filepath.Join(dir, "bunker.version"))
	return string(b)
}

func TestSnapshotOnVersionChange(t *testing.T) {
	data, bak := t.TempDir(), t.TempDir()
	SetBackupDir(bak)
	t.Cleanup(func() { SetBackupDir("") })
	db := openSave(t, data)
	if err := migrations.Up(context.Background(), db); err != nil {
		t.Fatal(err)
	}
	os.WriteFile(filepath.Join(data, "bunker.version"), []byte("0.9.0"), 0644)
	if err := upSaveDatabase(context.Background(), db, data, "1.0.0"); err != nil {
		t.Fatal(err)
	}
	if n := len(updateSnapshots(bak)); n != 1 {
		t.Fatalf("want 1 update snapshot, got %d", n)
	}
	if v := savedVersion(t, data); v != "1.0.0" {
		t.Fatalf("bunker.version = %q", v)
	}
	if err := upSaveDatabase(context.Background(), db, data, "1.0.0"); err != nil {
		t.Fatal(err)
	}
	if n := len(updateSnapshots(bak)); n != 1 {
		t.Fatalf("the same version must not snapshot again, got %d", n)
	}
}

func TestSnapshotIsAReadableCopy(t *testing.T) {
	data, bak := t.TempDir(), t.TempDir()
	db := openSave(t, data)
	migrations.Up(context.Background(), db)
	if err := prepareSaveDatabase(db, data, bak, "1.0.0"); err != nil {
		t.Fatal(err)
	}
	snaps := updateSnapshots(bak)
	if len(snaps) != 1 {
		t.Fatalf("want 1 snapshot, got %d", len(snaps))
	}
	copyDB, err := database.Open(snaps[0])
	if err != nil {
		t.Fatal(err)
	}
	defer copyDB.Close()
	var n int
	if err := copyDB.QueryRow(`SELECT COUNT(*) FROM goose_db_version`).Scan(&n); err != nil || n == 0 {
		t.Fatalf("snapshot has no migration history: %v %d", err, n)
	}
}

func TestSnapshotWhenVersionFileMissingOnExistingSave(t *testing.T) {
	data, bak := t.TempDir(), t.TempDir()
	db := openSave(t, data)
	migrations.Up(context.Background(), db)
	if err := prepareSaveDatabase(db, data, bak, "1.0.0"); err != nil {
		t.Fatal(err)
	}
	if n := len(updateSnapshots(bak)); n != 1 {
		t.Fatalf("a save from before 1.0 must be snapshotted, got %d", n)
	}
}

func TestNoSnapshotForNewPlayer(t *testing.T) {
	data, bak := t.TempDir(), t.TempDir()
	db := openSave(t, data)
	if err := prepareSaveDatabase(db, data, bak, "1.0.0"); err != nil {
		t.Fatal(err)
	}
	if n := len(updateSnapshots(bak)); n != 0 {
		t.Fatalf("new player: want no snapshot, got %d", n)
	}
}

func TestKeepsThreeUpdateSnapshots(t *testing.T) {
	data, bak := t.TempDir(), t.TempDir()
	SetBackupDir(bak)
	t.Cleanup(func() { SetBackupDir("") })
	db := openSave(t, data)
	migrations.Up(context.Background(), db)
	for _, v := range []string{"1.0.1", "1.0.2", "1.0.3", "1.0.4", "1.0.5"} {
		if err := upSaveDatabase(context.Background(), db, data, v); err != nil {
			t.Fatal(err)
		}
	}
	if n := len(updateSnapshots(bak)); n != 3 {
		t.Fatalf("want 3 kept, got %d", n)
	}
}

func TestNoSnapshotFolderRefusesToMigrate(t *testing.T) {
	data := t.TempDir()
	SetBackupDir("")
	db := openSave(t, data)
	migrations.Up(context.Background(), db)
	if err := upSaveDatabase(context.Background(), db, data, "1.0.0"); err == nil {
		t.Fatal("updated a save without a snapshot")
	}
	if v := savedVersion(t, data); v != "" {
		t.Fatalf("bunker.version written after a refusal: %q", v)
	}
}

func TestRefusesNewerDatabase(t *testing.T) {
	data, bak := t.TempDir(), t.TempDir()
	db := openSave(t, data)
	migrations.Up(context.Background(), db)
	os.WriteFile(filepath.Join(data, "bunker.version"), []byte("9.0.0"), 0644)
	if _, err := db.Exec(`INSERT INTO goose_db_version (version_id, is_applied) VALUES (99991231000000, 1)`); err != nil {
		t.Fatal(err)
	}
	err := prepareSaveDatabase(db, data, bak, "1.0.0")
	if err == nil || !strings.Contains(err.Error(), "newer Bunker (9.0.0)") {
		t.Fatalf("want refusal, got %v", err)
	}
	if n := len(updateSnapshots(bak)); n != 0 {
		t.Fatalf("a refusal must not snapshot, got %d", n)
	}
}

func TestImportRefusesSaveFromNewerBunker(t *testing.T) {
	Stop()
	root := t.TempDir()
	saves, backup := filepath.Join(root, "saves"), filepath.Join(root, "backup")
	newSaves(t, saves, "this-device", 1)
	newSaves(t, backup, "this-device", 2)
	db, err := database.Open(filepath.Join(backup, "game.db"))
	if err != nil {
		t.Fatal(err)
	}
	db.Exec(`INSERT INTO goose_db_version (version_id, is_applied) VALUES (99991231000000, 1)`)
	database.Checkpoint(db)
	db.Close()
	if e := ImportSaves(saves, filepath.Join(backup, "game.db")); !strings.Contains(e, "newer Bunker") {
		t.Fatalf("want a refusal, got %q", e)
	}
	if got := player(t, saves); got != "this-device/1" {
		t.Fatalf("the current save was replaced: %q", got)
	}
}

func TestQueryErrorIsNotANewPlayer(t *testing.T) {
	data, bak := t.TempDir(), t.TempDir()
	db := openSave(t, data)
	migrations.Up(context.Background(), db)
	db.Close() // every query now fails
	if err := prepareSaveDatabase(db, data, bak, "1.0.0"); err == nil {
		t.Fatal("a database that can't be read was treated as a new player")
	}
}
