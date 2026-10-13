package database

import (
	"context"
	"path/filepath"
	"testing"
)

// Every pooled connection gets the pragmas, not just the first one.
func TestPragmasOnEveryConnection(t *testing.T) {
	db, err := Open(filepath.Join(t.TempDir(), "game.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	ctx := context.Background()
	var conns []interface{ Close() error }
	for i := 0; i < 3; i++ {
		c, err := db.Conn(ctx)
		if err != nil {
			t.Fatal(err)
		}
		conns = append(conns, c)
		var fk, busy int
		var mode string
		if err := c.QueryRowContext(ctx, "PRAGMA foreign_keys").Scan(&fk); err != nil {
			t.Fatal(err)
		}
		if err := c.QueryRowContext(ctx, "PRAGMA busy_timeout").Scan(&busy); err != nil {
			t.Fatal(err)
		}
		if err := c.QueryRowContext(ctx, "PRAGMA journal_mode").Scan(&mode); err != nil {
			t.Fatal(err)
		}
		if fk != 1 || busy != 5000 || mode != "wal" {
			t.Errorf("connection %d: foreign_keys=%d busy_timeout=%d journal_mode=%s", i, fk, busy, mode)
		}
	}
	for _, c := range conns {
		c.Close()
	}
}
