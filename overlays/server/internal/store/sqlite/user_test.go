package sqlite

import (
	"context"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/migrations"
)

// Concurrent updates of one player all land: none reads the save while
// another is between its read and its write.
func TestUpdateUserConcurrent(t *testing.T) {
	db, err := database.Open(filepath.Join(t.TempDir(), "game.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err := migrations.Up(context.Background(), db); err != nil {
		t.Fatal(err)
	}
	s := New(db, time.Now)
	uid, err := s.CreateUser("test-uuid", model.ClientPlatform{})
	if err != nil {
		t.Fatal(err)
	}
	start, err := s.LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}
	const n = 20
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, err := s.UpdateUser(uid, func(u *store.UserState) { u.Gem.FreeGem++ }); err != nil {
				t.Error(err)
			}
		}()
	}
	wg.Wait()
	u, err := s.LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}
	if u.Gem.FreeGem != start.Gem.FreeGem+n {
		t.Fatalf("free gems %d, want %d", u.Gem.FreeGem, start.Gem.FreeGem+n)
	}
}
