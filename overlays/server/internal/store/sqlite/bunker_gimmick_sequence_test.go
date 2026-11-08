package sqlite

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/migrations"
)

// EnsureGimmickSequence writes one sequence row without loading the save,
// leaves an existing (maybe cleared) row alone, and stops at the row cap.
func TestEnsureGimmickSequence(t *testing.T) {
	ctx := context.Background()
	db, err := database.Open(filepath.Join(t.TempDir(), "game.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err := migrations.Up(ctx, db); err != nil {
		t.Fatal(err)
	}
	s := New(db, time.Now)
	uid, err := s.CreateUser("test-uuid", model.ClientPlatform{})
	if err != nil {
		t.Fatal(err)
	}

	if added, ok, err := s.EnsureGimmickSequence(uid, 5, 50, 3); err != nil || !ok || !added {
		t.Fatalf("first: added %v ok %v err %v", added, ok, err)
	}
	if added, ok, err := s.EnsureGimmickSequence(uid, 5, 50, 3); err != nil || !ok || added {
		t.Fatalf("again: added %v ok %v err %v", added, ok, err)
	}
	// A cleared row stays cleared.
	key := store.GimmickSequenceKey{GimmickSequenceScheduleId: 5, GimmickSequenceId: 50}
	if _, err := s.UpdateUser(uid, func(u *store.UserState) {
		u.Gimmick.Sequences[key] = store.GimmickSequenceState{Key: key, IsGimmickSequenceCleared: true, ClearDatetime: 9}
	}); err != nil {
		t.Fatal(err)
	}
	if added, ok, _ := s.EnsureGimmickSequence(uid, 5, 50, 3); !ok || added {
		t.Fatalf("cleared row: added %v ok %v", added, ok)
	}
	u, _ := s.LoadUser(uid)
	if !u.Gimmick.Sequences[key].IsGimmickSequenceCleared {
		t.Fatalf("cleared row overwritten: %+v", u.Gimmick.Sequences[key])
	}
	// The cap: with 3 rows the save is full, and a new row is left to the caller.
	for _, id := range []int32{51, 52} {
		if added, ok, _ := s.EnsureGimmickSequence(uid, 5, id, 3); !ok || !added {
			t.Fatalf("row %d not added", id)
		}
	}
	if added, ok, _ := s.EnsureGimmickSequence(uid, 5, 53, 3); ok || added {
		t.Fatalf("over the cap: added %v ok %v", added, ok)
	}
	u, _ = s.LoadUser(uid)
	if len(u.Gimmick.Sequences) != 3 {
		t.Fatalf("%d sequence rows, want 3", len(u.Gimmick.Sequences))
	}
}
