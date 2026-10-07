package missions

import (
	"context"
	"io"
	"os"
	"path/filepath"
	"testing"
	"time"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/store/sqlite"
	"lunar-tear/server/migrations"
)

// Runs against real game data: BUNKER_TEST_MASTER is a (patched) master data
// .bin.e and BUNKER_TEST_SAVE a game.db with one player. Skipped without them.
func realSave(t *testing.T) (*Catalog, *sqlite.SQLiteStore, int64, *runtime.Holder) {
	master, save := os.Getenv("BUNKER_TEST_MASTER"), os.Getenv("BUNKER_TEST_SAVE")
	if master == "" || save == "" {
		t.Skip("BUNKER_TEST_MASTER and BUNKER_TEST_SAVE not set")
	}
	dir := t.TempDir()
	for _, f := range []struct{ from, to string }{{master, "master.bin.e"}, {save, "game.db"}} {
		in, err := os.Open(f.from)
		if err != nil {
			t.Fatal(err)
		}
		out, _ := os.Create(filepath.Join(dir, f.to))
		io.Copy(out, in)
		in.Close()
		out.Close()
	}
	h, err := runtime.NewHolder(filepath.Join(dir, "master.bin.e"))
	if err != nil {
		t.Fatal(err)
	}
	SetHolder(h)
	cat := Current()
	if cat == nil {
		t.Fatal("no catalog")
	}
	db, err := database.Open(filepath.Join(dir, "game.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	if err := migrations.Up(context.Background(), db); err != nil {
		t.Fatal(err)
	}
	var uid int64
	if err := db.QueryRow(`SELECT user_id FROM users ORDER BY user_id LIMIT 1`).Scan(&uid); err != nil {
		t.Fatal(err)
	}
	return cat, sqlite.New(db, time.Now), uid, h
}

func status(u store.UserState) (cleared, received int) {
	for _, m := range u.Missions {
		switch m.MissionProgressStatusType {
		case StatusClear:
			cleared++
		case StatusRewardReceived:
			received++
		}
	}
	return
}

func TestRealSave(t *testing.T) {
	cat, st, uid, h := realSave(t)
	now := time.Now().UnixMilli()

	// Backfill from what the save already did.
	u, err := st.UpdateUser(uid, func(u *store.UserState) {
		before := store.CloneUserState(*u)
		cat.Track(&before, u, "/apb.api.user.UserService/GameStart", nil, now)
	})
	if err != nil {
		t.Fatal(err)
	}
	cleared, _ := status(u)
	for id, m := range u.Missions {
		if m.MissionProgressStatusType == StatusClear {
			t.Logf("CLEARED %d %d/%d", id, m.ProgressValue, cat.ById[id].ClearConditionValue)
		}
	}
	t.Logf("after backfill: %d mission records, %d cleared, version %d", len(u.Missions), cleared, u.Ext.MissionsVersion)
	if u.Ext.MissionsVersion != trackVersion || cleared == 0 {
		t.Fatalf("backfill did nothing")
	}
	// Clear a main quest once: an active daily quest mission counts it.
	var daily *Mission
	for _, m := range cat.ByKind["quest"] {
		if m.Daily() && len(m.Rule.Costumes) == 0 && cat.active(m, &u, now) {
			daily = m
			break
		}
	}
	if daily == nil {
		t.Fatal("no active daily quest mission")
	}
	var mainQuest int32
	for id, places := range cat.places {
		if len(places) > 0 && places[0].MainChapter != 0 && cat.QuestMatches(daily.Rule.Quest, id) {
			mainQuest = id
			break
		}
	}
	progress := u.Missions[daily.MissionId].ProgressValue
	u, err = st.UpdateUser(uid, func(u *store.UserState) {
		before := store.CloneUserState(*u)
		q := u.Quests[mainQuest]
		q.QuestId = mainQuest
		q.ClearCount++
		u.Quests[mainQuest] = q
		cat.Track(&before, u, "/apb.api.quest.QuestService/FinishMainQuest", &pb.FinishMainQuestRequest{QuestId: mainQuest}, now+1)
	})
	if err != nil {
		t.Fatal(err)
	}
	if m := u.Missions[daily.MissionId]; m.ProgressValue != progress+1 && m.MissionProgressStatusType < StatusClear {
		t.Fatalf("daily mission %d did not count quest %d: %+v", daily.MissionId, mainQuest, m)
	}
	t.Logf("daily mission %d after one main quest: %+v", daily.MissionId, u.Missions[daily.MissionId])

	// Receive every cleared mission: statuses move to received and rewards arrive.
	var ids []int32
	for id, m := range u.Missions {
		if m.MissionProgressStatusType == StatusClear {
			ids = append(ids, id)
		}
	}
	gemsBefore := u.Gem.FreeGem
	var got []Reward
	u, err = st.UpdateUser(uid, func(u *store.UserState) {
		got = cat.ReceiveMissions(u, h.Get().QuestHandler.Granter, ids, now+2)
	})
	if err != nil {
		t.Fatal(err)
	}
	cleared, received := status(u)
	t.Logf("received %d missions: %d rewards, free gems %d -> %d; now %d cleared, %d received", len(ids), len(got), gemsBefore, u.Gem.FreeGem, cleared, received)
	if received < len(ids) || len(got) == 0 {
		t.Fatalf("rewards not received")
	}
	for id, p := range u.Ext.MissionPass {
		t.Logf("mission pass %d: %d points, level %d", id, p.Point, cat.PassLevel(id, p.Point))
	}

	// Reloading keeps the mission state and the Bunker save document.
	again, err := st.LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}
	if len(again.Missions) != len(u.Missions) || !again.Ext.Equal(u.Ext) {
		t.Fatalf("state not persisted: %d vs %d missions", len(again.Missions), len(u.Missions))
	}

	// A new day resets the daily missions.
	tomorrow := startOfDay(now) + 24*3600*1000 + 1000
	u, _ = st.UpdateUser(uid, func(u *store.UserState) {
		before := store.CloneUserState(*u)
		cat.Track(&before, u, "/apb.api.user.UserService/GameStart", nil, tomorrow)
	})
	if m := u.Missions[daily.MissionId]; m.MissionProgressStatusType != StatusInProgress || m.ProgressValue != 0 {
		t.Fatalf("daily mission not reset the next day: %+v", m)
	}
}

func TestQuestFilter(t *testing.T) {
	cat, _, _, _ := realSave(t)
	// Find an event chapter quest and check the filters that should and shouldn't match it.
	for id, places := range cat.places {
		p := places[0]
		if p.EventChapter == 0 || p.Order != 1 {
			continue
		}
		yes := []*QuestFilter{nil, {}, {Event: true}, {EventTypes: []int32{p.EventType}}, {EventChapters: []int32{p.EventChapter}, Order: 1, Diff: []int32{p.Difficulty}}}
		no := []*QuestFilter{{Main: true}, {EventChapters: []int32{p.EventChapter}, Order: 2}, {EventChapters: []int32{-1}}}
		for _, f := range yes {
			if !cat.QuestMatches(f, id) {
				t.Errorf("quest %d %+v should match %+v", id, p, f)
			}
		}
		for _, f := range no {
			if cat.QuestMatches(f, id) {
				t.Errorf("quest %d %+v should not match %+v", id, p, f)
			}
		}
		break
	}
}
