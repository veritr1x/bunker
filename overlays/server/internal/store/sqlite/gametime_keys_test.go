package sqlite

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/migrations"
)

// A save with old UTC week keys is read with GMT-8 keys, and the next update
// stores them that way.
func TestOldWeekKeysAreUpgraded(t *testing.T) {
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
	oldWeek := gametime.WeeklyVersion(gametime.NowMillis()) - 8*3600*1000 // this week's Monday 00:00 UTC
	if _, err := db.Exec(`INSERT INTO user_big_hunt_weekly_max_scores (user_id, big_hunt_weekly_version, attribute_type, max_score, latest_version) VALUES (?,?,?,?,?)`,
		uid, oldWeek, 2, 777, 1); err != nil {
		t.Fatal(err)
	}
	newKey := store.BigHuntWeeklyScoreKey{BigHuntWeeklyVersion: gametime.UpgradeWeekVersion(oldWeek), AttributeType: 2}
	u, err := s.LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}
	if u.BigHuntWeeklyMaxScores[newKey].MaxScore != 777 || len(u.BigHuntWeeklyMaxScores) != 1 {
		t.Fatalf("loaded %+v", u.BigHuntWeeklyMaxScores)
	}
	if _, err := s.UpdateUser(uid, func(*store.UserState) {}); err != nil {
		t.Fatal(err)
	}
	var n int
	if err := db.QueryRow(`SELECT COUNT(*) FROM user_big_hunt_weekly_max_scores WHERE user_id = ? AND big_hunt_weekly_version = ? AND max_score = 777`,
		uid, newKey.BigHuntWeeklyVersion).Scan(&n); err != nil || n != 1 {
		t.Fatalf("upgraded row stored %d times (%v)", n, err)
	}
	if err := db.QueryRow(`SELECT COUNT(*) FROM user_big_hunt_weekly_max_scores WHERE user_id = ? AND big_hunt_weekly_version = ?`, uid, oldWeek).Scan(&n); err != nil || n != 0 {
		t.Fatalf("old row left %d (%v)", n, err)
	}
}
