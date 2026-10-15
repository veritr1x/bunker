package mobile

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"lunar-tear/server/migrations"
)

// Before a new Bunker version first opens a save, the save is copied to the
// folder Pod Programs lists its snapshots from ("Before update"); then it is
// migrated and bunker.version records the version. A save that a newer Bunker
// already migrated is refused, so an older build never damages it.

var backupDir struct {
	sync.Mutex
	path string
}

// SetBackupDir sets where the snapshot before an update goes. Call before Start.
func SetBackupDir(dir string) string {
	backupDir.Lock()
	defer backupDir.Unlock()
	backupDir.path = dir
	return ""
}

func currentBackupDir() string {
	backupDir.Lock()
	defer backupDir.Unlock()
	return backupDir.path
}

// keptUpdateSnapshots is how many "Before update" snapshots stay; Pod Programs'
// own retention leaves them alone.
const keptUpdateSnapshots = 3

const versionFile = "bunker.version"

// upSaveDatabase guards, snapshots, migrates and records the version.
func upSaveDatabase(ctx context.Context, db *sql.DB, dataRoot, version string) error {
	if err := prepareSaveDatabase(db, dataRoot, currentBackupDir(), version); err != nil {
		return err
	}
	if err := migrations.Up(ctx, db); err != nil {
		return fmt.Errorf("prepare save database: %w", err)
	}
	return os.WriteFile(filepath.Join(dataRoot, versionFile), []byte(version), 0644)
}

// prepareSaveDatabase refuses a save from a newer build and snapshots an
// existing save into backups when the version changed. A new player (no
// migration history yet) needs neither.
func prepareSaveDatabase(db *sql.DB, dataRoot, backups, version string) error {
	var table string
	switch err := db.QueryRow(`SELECT name FROM sqlite_master WHERE type='table' AND name='goose_db_version'`).Scan(&table); {
	case errors.Is(err, sql.ErrNoRows):
		return nil
	case err != nil:
		return fmt.Errorf("read the save: %w", err)
	}
	recorded := savedBunkerVersion(dataRoot)
	if err := refuseNewerSave(db, recorded); err != nil {
		return err
	}
	if recorded == version {
		return nil
	}
	if backups == "" {
		return fmt.Errorf("no snapshot folder set, so the save was not updated")
	}
	if err := os.MkdirAll(backups, 0755); err != nil {
		return fmt.Errorf("snapshot before update: %w", err)
	}
	// The name matches Pod Programs' snapshots: backup_<time to the microsecond>_<reason>.db.
	now := time.Now()
	target := filepath.Join(backups, fmt.Sprintf("backup_%s-%06d_update.db", now.Format("2006-01-02T15-04-05"), now.Nanosecond()/1000))
	if _, err := db.Exec(`VACUUM INTO ?`, target); err != nil {
		os.Remove(target)
		return fmt.Errorf("snapshot before update: %w", err)
	}
	pruneUpdateSnapshots(backups)
	return nil
}

// refuseNewerSave fails for a save that a newer Bunker already migrated
// (made is that version, if known), so this build never opens it.
func refuseNewerSave(db *sql.DB, made string) error {
	var applied sql.NullInt64
	if err := db.QueryRow(`SELECT MAX(version_id) FROM goose_db_version WHERE is_applied = 1`).Scan(&applied); err != nil {
		return fmt.Errorf("read the save's version: %w", err)
	}
	if applied.Valid && applied.Int64 > newestKnownMigration() {
		if made == "" {
			made = "unknown version"
		}
		return fmt.Errorf("This save was made by a newer Bunker (%s). Install that version or newer, or restore a snapshot in Pod Programs.", made)
	}
	return nil
}

func savedBunkerVersion(dataRoot string) string {
	b, err := os.ReadFile(filepath.Join(dataRoot, versionFile))
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(b))
}

// newestKnownMigration is the highest version among this build's migrations.
func newestKnownMigration() int64 {
	var newest int64
	entries, _ := fs.ReadDir(migrations.FS, ".")
	for _, e := range entries {
		if n, err := strconv.ParseInt(strings.SplitN(e.Name(), "_", 2)[0], 10, 64); err == nil && n > newest {
			newest = n
		}
	}
	return newest
}

func pruneUpdateSnapshots(dir string) {
	m, _ := filepath.Glob(filepath.Join(dir, "backup_*_update.db"))
	sort.Strings(m) // the time in the name sorts oldest first
	for len(m) > keptUpdateSnapshots {
		os.Remove(m[0])
		m = m[1:]
	}
}
