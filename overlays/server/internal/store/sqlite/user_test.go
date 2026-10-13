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

// A shard conversion's obtained Medals are saved on their own (the summon
// screen's popup needs them).
func TestConvertedMedalObtainSaved(t *testing.T) {
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
	if _, err := s.UpdateUser(uid, func(u *store.UserState) {
		u.Gacha.ConvertedGachaMedal = store.ConvertedGachaMedalState{
			ConvertedMedalPossession: []store.ConsumableItemState{{ConsumableItemId: 8003, Count: 170}},
			ObtainPossession:         &store.ConsumableItemState{ConsumableItemId: 2, Count: 170},
		}
	}); err != nil {
		t.Fatal(err)
	}
	u, err := s.LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}
	if o := u.Gacha.ConvertedGachaMedal.ObtainPossession; o == nil || o.ConsumableItemId != 2 || o.Count != 170 {
		t.Fatalf("obtained Medals not saved: %+v", o)
	}
	if _, err := s.UpdateUser(uid, func(u *store.UserState) { u.Gacha.ConvertedGachaMedal = store.ConvertedGachaMedalState{} }); err != nil {
		t.Fatal(err)
	}
	if u, _ = s.LoadUser(uid); u.Gacha.ConvertedGachaMedal.ObtainPossession != nil {
		t.Fatal("cleared conversion still saved")
	}
}
