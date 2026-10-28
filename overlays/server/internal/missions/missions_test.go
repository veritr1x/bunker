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

// afterLastLogin is now, or just after the save's last login when that is later:
// the Original calendar can move a save's clock ahead of the real one.
func afterLastLogin(t *testing.T, st *sqlite.SQLiteStore, uid int64) int64 {
	t.Helper()
	u, err := st.LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}
	return max(time.Now().UnixMilli(), u.Login.LastLoginDatetime+1000)
}

func TestRealSave(t *testing.T) {
	cat, st, uid, h := realSave(t)
	now := afterLastLogin(t, st, uid)

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
	// The day's first request is a login: the daily "Log in" missions clear.
	var logins int
	for _, m := range cat.ByKind["login"] {
		if !m.Daily() || !cat.active(m, &u, tomorrow) {
			continue
		}
		logins++
		if rec := u.Missions[m.MissionId]; rec.MissionProgressStatusType != StatusClear {
			t.Errorf("daily login mission %d not cleared the next day: %+v", m.MissionId, rec)
		}
	}
	if logins == 0 || u.Login.TotalLoginCount != again.Login.TotalLoginCount+1 {
		t.Fatalf("%d daily login missions; logins %d -> %d", logins, again.Login.TotalLoginCount, u.Login.TotalLoginCount)
	}
	// Later requests the same day are not more logins.
	u, _ = st.UpdateUser(uid, func(u *store.UserState) {
		before := store.CloneUserState(*u)
		cat.Track(&before, u, "/apb.api.user.UserService/GameStart", nil, tomorrow+1000)
	})
	if u.Login.TotalLoginCount != again.Login.TotalLoginCount+1 {
		t.Fatalf("second request of the day counted as a login: %d", u.Login.TotalLoginCount)
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

// first returns a mission with this rule kind (and, if given, a matching rule).
func first(t *testing.T, cat *Catalog, kind string, ok func(*Mission) bool) *Mission {
	t.Helper()
	for _, m := range cat.ByKind[kind] {
		if ok == nil || ok(m) {
			return m
		}
	}
	t.Fatalf("no %s mission", kind)
	return nil
}

func TestCountedKinds(t *testing.T) {
	cat, st, uid, _ := realSave(t)
	u, err := st.LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}

	// Bosses: a quest whose battles field bosses counts them when won, not when skipped.
	var bossQuest int32
	for id, n := range cat.questBosses {
		if n > 0 {
			bossQuest = id
			break
		}
	}
	if bossQuest == 0 {
		t.Fatal("no quest with bosses")
	}
	boss := first(t, cat, "defeat_boss", nil)
	won := &counts{clears: []questClear{{questId: bossQuest, count: 1}}}
	skipped := &counts{clears: []questClear{{questId: bossQuest, count: 1, skipped: true}}}
	if n := cat.amountFor(boss, won); n != cat.questBosses[bossQuest] {
		t.Errorf("defeat_boss: quest %d won counts %d, want %d", bossQuest, n, cat.questBosses[bossQuest])
	}
	if n := cat.amountFor(boss, skipped); n != 0 {
		t.Errorf("defeat_boss: skipped quest counts %d", n)
	}

	// Explorations: a filtered mission counts only its explores.
	shooting := first(t, cat, "explore_finish", func(m *Mission) bool { return len(m.Rule.Explores) == 1 && m.Rule.Explores[0] == 1 })
	if n := cat.amountFor(shooting, &counts{explores: map[int32]int64{1: 1, 2: 1}}); n != 1 {
		t.Errorf("explore_finish Shooting: %d, want 1", n)
	}

	// Concert taps: the best performance, not the sum.
	live := first(t, cat, "rhythm_tap", nil)
	before := store.CloneUserState(u)
	for _, taps := range []int32{20, 10} {
		prev := store.CloneUserState(u)
		cat.Track(&prev, &u, "/apb.api.mission.MissionService/UpdateMissionProgress", &pb.UpdateMissionProgressRequest{
			PictureBookMeasurableValues: &pb.PictureBookMeasurableValues{RhythmInteractionMeasurableValues: &pb.RhythmInteractionMeasurableValues{LiveTypeId: live.Rule.LiveType, TapCount: taps}},
		}, time.Now().UnixMilli())
	}
	if cat.active(live, &u, time.Now().UnixMilli()) {
		if p := u.Missions[live.MissionId].ProgressValue; p != 20 && u.Missions[live.MissionId].MissionProgressStatusType < StatusClear {
			t.Errorf("rhythm_tap progress %d, want 20", p)
		}
	}
	u = before

	// Arena: plays, wins and a streak a loss resets.
	streak := first(t, cat, "pvp_streak", func(m *Mission) bool { return m.ClearConditionValue > 3 })
	u.Ext.MissionsVersion = trackVersion
	delete(u.Missions, streak.MissionId)
	now := time.Now().UnixMilli()
	battle := func(win bool) {
		prev := store.CloneUserState(u)
		u.Ext.Pvp.AttackLog = append([]store.PvpLog{{PlayerId: 9_000_000_001, Victory: win, Datetime: now}}, u.Ext.Pvp.AttackLog...)
		now++
		cat.Track(&prev, &u, "/apb.api.pvp.PvpService/FinishBattle", &pb.FinishBattleRequest{IsVictory: win}, now)
	}
	if !cat.active(streak, &u, now) {
		t.Skipf("streak mission %d not active", streak.MissionId)
	}
	battle(true)
	battle(true)
	if p := u.Missions[streak.MissionId].ProgressValue; p != 2 {
		t.Errorf("streak after two wins: %d", p)
	}
	battle(false)
	if p := u.Missions[streak.MissionId].ProgressValue; p != 0 {
		t.Errorf("streak after a loss: %d", p)
	}

	// Arena rank: cleared once the season's best rank is at or above the target.
	rank := first(t, cat, "pvp_rank", nil)
	u.Ext.Pvp.MaxSeasonRank = rank.ClearConditionValue + 1
	if v := cat.stateValue(rank, &u); v != 0 {
		t.Errorf("pvp_rank below target: %d", v)
	}
	u.Ext.Pvp.MaxSeasonRank = rank.ClearConditionValue
	if v := cat.stateValue(rank, &u); v != int64(rank.ClearConditionValue) {
		t.Errorf("pvp_rank at target: %d", v)
	}

	// Values read from the save.
	for _, kind := range []string{"library", "report", "costume_ability_level", "board_panel", "explore_score", "big_hunt_score"} {
		t.Logf("%s: %d", kind, cat.stateValue(first(t, cat, kind, nil), &u))
	}
	if cat.stateValue(first(t, cat, "library", nil), &u) == 0 {
		t.Error("encyclopedia empty for a played save")
	}
	// A character's Stone Tower panels are part of all panels.
	all := cat.stateValue(first(t, cat, "board_panel", func(m *Mission) bool { return len(m.Rule.Characters) == 0 }), &u)
	one := first(t, cat, "board_panel", func(m *Mission) bool { return len(m.Rule.Characters) > 0 })
	if v := cat.stateValue(one, &u); v > all {
		t.Errorf("board panels for %v %v: %d > all %d", one.Rule.Characters, one.Rule.BoardTypes, v, all)
	}
	u.FacebookId = 0
	transfer := first(t, cat, "data_transfer", nil)
	if cat.stateValue(transfer, &u) != 0 {
		t.Error("data transfer without an account")
	}
	u.FacebookId = 1
	if cat.stateValue(transfer, &u) != 1 {
		t.Error("data transfer with an account")
	}

	// Friend cheers and cage counters on other requests.
	cheer := first(t, cat, "cheer_friend", nil)
	prev := store.CloneUserState(u)
	u.Ext.Friends.TotalSent += 2
	if n := cat.amountFor(cheer, collect(&prev, &u, "/apb.api.friend.FriendService/BulkCheerFriend", nil)); n != 2 {
		t.Errorf("cheer_friend: %d", n)
	}
	walk := first(t, cat, "cage_walk", nil)
	c := collect(&u, &u, "/apb.api.banner.BannerService/GetMamaBanner", &pb.GetMamaBannerRequest{CageMeasurableValues: &pb.CageMeasurableValues{RunningDistanceMeters: 30}})
	if n := cat.amountFor(walk, c); n != 30 {
		t.Errorf("cage_walk from GetMamaBanner: %d", n)
	}

	// The deck used in battle is remembered for the profile.
	recordLastDeck(&u, &pb.FinishWaveRequest{UserPartyResultInfoList: []*pb.UserPartyResultInfo{{DeckType: 1, UserDeckNumber: 3}}})
	if u.Ext.LastDeck != (store.LastDeckState{DeckType: 1, UserDeckNumber: 3}) {
		t.Errorf("last deck %+v", u.Ext.LastDeck)
	}
}

func TestQuestFilterQuests(t *testing.T) {
	cat, _, _, _ := realSave(t)
	m := cat.ById[28909] // "Clear Levania Dark Lair: Hard"
	if m == nil || m.Rule.Quest == nil || len(m.Rule.Quest.Quests) != 1 {
		t.Fatalf("mission 28909 rule %+v", m)
	}
	q := m.Rule.Quest.Quests[0]
	if !cat.QuestMatches(m.Rule.Quest, q) || cat.QuestMatches(m.Rule.Quest, q-1) {
		t.Errorf("quest list filter %v", m.Rule.Quest.Quests)
	}
	// "with only Akeha in your loadout": a deck with someone else does not count.
	only := cat.ById[500057]
	if only == nil || !only.Rule.Only {
		t.Fatalf("mission 500057 rule %+v", only)
	}
	var akeha, other int32
	for co, ch := range cat.costumeChar {
		if ch == 1015 && akeha == 0 {
			akeha = co
		} else if ch != 1015 && ch != 0 && other == 0 {
			other = co
		}
	}
	target := only.Rule.Quest.Quests[0]
	if n := cat.amountFor(only, &counts{clears: []questClear{{questId: target, count: 1, costumes: []int32{akeha}}}}); n != 1 {
		t.Errorf("only Akeha: %d", n)
	}
	if n := cat.amountFor(only, &counts{clears: []questClear{{questId: target, count: 1, costumes: []int32{akeha, other}}}}); n != 0 {
		t.Errorf("Akeha and another: %d", n)
	}
}

func TestNewRules(t *testing.T) {
	cat, st, uid, _ := realSave(t)
	u, err := st.LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}
	rule := func(id int32) Rule {
		t.Helper()
		m := cat.ById[id]
		if m == nil || m.Rule.Kind == "" {
			t.Fatalf("mission %d has no rule", id)
		}
		return m.Rule
	}
	// Named weapons and costumes ("Enhance Spear of Freezing Mist's weapon skills", "Flurry of Indulgence Dagger 1 times").
	for id, want := range map[int32]string{1333: "weapon_skill", 3320: "weapon_skill", 9012: "weapon_skill", 5721: "weapon_limit_break", 3814: "costume_skill"} {
		if r := rule(id); r.Kind != want || len(r.Weapons)+len(r.Costumes) == 0 {
			t.Errorf("mission %d rule %+v", id, r)
		}
	}
	if r := rule(1333); !contains(r.Weapons, 220061) {
		t.Errorf("Spear of Freezing Mist: %v", r.Weapons)
	}

	// Collections: the costumes m_complete_mission_group lists, owned.
	group := cat.ById[900201] // Rion and Gayle
	if r := rule(900201); r.Kind != "costume_collect" || len(r.Costumes) != 2 {
		t.Fatalf("collection rule %+v", r)
	}
	v := store.CloneUserState(u)
	v.Costumes = map[string]store.CostumeState{"a": {CostumeId: group.Rule.Costumes[0]}, "b": {CostumeId: group.Rule.Costumes[0]}}
	if n := cat.stateValue(group, &v); n != 1 {
		t.Errorf("one of two costumes (twice): %d", n)
	}
	v.Costumes["c"] = store.CostumeState{CostumeId: group.Rule.Costumes[1]}
	if n := cat.stateValue(group, &v); n != 2 {
		t.Errorf("both costumes: %d", n)
	}

	// Chapter 4 without the first-defeat tutorials: its last Normal quest.
	ch4 := cat.ById[460002]
	var last int32
	for id, places := range cat.places {
		for _, p := range places {
			if p.MainChapter == 5 && p.Difficulty == 1 && p.Rank == ch4.Rule.Quest.Order {
				last = id
			}
		}
	}
	won := &counts{clears: []questClear{{questId: last, count: 1}}, tutorials: map[int32]store.TutorialProgressState{1: {}}}
	if last == 0 || cat.amountFor(ch4, won) != 1 {
		t.Errorf("chapter 4 last quest %d without the tutorials: %d", last, cat.amountFor(ch4, won))
	}
	won.tutorials[44] = store.TutorialProgressState{TutorialType: 44}
	if cat.amountFor(ch4, won) != 0 {
		t.Error("counted after the first-defeat tutorial")
	}

	// Quest 3 of an event on EX Hard: EX Hard numbers on after Very Hard (31, 32, 33...).
	ex := cat.ById[500013]
	var third, second int32
	for id, places := range cat.places {
		for _, p := range places {
			if p.EventChapter == 501 && p.Difficulty == 4 {
				switch p.Rank {
				case 3:
					third = id
				case 2:
					second = id
				}
			}
		}
	}
	if third == 0 || !cat.QuestMatches(ex.Rule.Quest, third) || cat.QuestMatches(ex.Rule.Quest, second) {
		t.Errorf("EX Hard quest 3: %d matches %v, quest 2 %d matches %v", third, cat.QuestMatches(ex.Rule.Quest, third), second, cat.QuestMatches(ex.Rule.Quest, second))
	}
	// "Clear story quest 2-2": main story chapter 2, quest 2.
	if r := rule(7006); r.Quest == nil || len(r.Quest.MainChapters) != 1 || r.Quest.Order != 2 {
		t.Errorf("story quest 2-2: %+v", r.Quest)
	}

	// Profile messages, title screen, weapon locks, exploration score.
	set := func(msg string) *counts {
		return collect(&u, &u, "/apb.api.user.UserService/SetUserMessage", &pb.SetUserMessageRequest{Message: msg})
	}
	newYear, update := cat.ById[7004], cat.ById[1010901]
	if cat.amountFor(newYear, set("A happy  new year!")) != 1 || cat.amountFor(newYear, set("Hello")) != 0 || cat.amountFor(update, set("Hello")) != 1 {
		t.Error("profile message missions")
	}
	if n := cat.amountFor(cat.ById[7007], collect(&u, &u, "/apb.api.user.UserService/GameStart", nil)); n != 1 {
		t.Errorf("title screen: %d", n)
	}
	if n := cat.amountFor(cat.ById[7010], collect(&u, &u, "/apb.api.explore.ExploreService/FinishExplore", &pb.FinishExploreRequest{ExploreId: 1, Score: 12345})); n != 12345 {
		t.Errorf("exploration score: %d", n)
	}
	before := store.CloneUserState(u)
	after := store.CloneUserState(u)
	for id, w := range after.Weapons {
		before.Weapons[id] = store.WeaponState{WeaponId: w.WeaponId}
		w.IsProtected = true
		after.Weapons[id] = w
	}
	if n := cat.amountFor(cat.ById[7008], collect(&before, &after, "/apb.api.weapon.WeaponService/Protect", nil)); n != int64(len(after.Weapons)) || n == 0 {
		t.Errorf("weapon locks: %d of %d", n, len(after.Weapons))
	}
}

func TestPlayHistory(t *testing.T) {
	cat, st, uid, _ := realSave(t)
	u, err := st.LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}
	now := afterLastLogin(t, st, uid)
	counted := u.Ext.History[HistoryMissionsCompleted] // what the save already counted
	track := func(method string, req any) {
		prev := store.CloneUserState(u)
		now++
		cat.Track(&prev, &u, method, req, now)
	}
	// A save tracked before the history starts it from its missions.
	u.Ext.MissionsVersion = 3
	track("/apb.api.user.UserService/GameStart", nil)
	var done int64
	for _, m := range u.Missions {
		if m.MissionProgressStatusType >= StatusClear {
			done++
		}
	}
	// Daily missions completed on past days have reset since; a counter the save
	// already has stays when it is larger than the missions cleared now.
	if got := cat.HistoryValue(&u, HistoryMissionsCompleted); got != max(done, counted) || done == 0 {
		t.Errorf("missions completed %d, %d cleared, %d counted before", got, done, counted)
	}
	walk := cat.HistoryValue(&u, HistoryWalkDistance)
	track("/apb.api.mission.MissionService/UpdateMissionProgress", &pb.UpdateMissionProgressRequest{CageMeasurableValues: &pb.CageMeasurableValues{RunningDistanceMeters: 120}})
	if got := cat.HistoryValue(&u, HistoryWalkDistance); got != walk+120 {
		t.Errorf("walk distance %d -> %d", walk, got)
	}
	track("/apb.api.weapon.WeaponService/EnhanceSkill", &pb.EnhanceSkillRequest{})
	var itemShop int32
	for id, g := range cat.shopGroups {
		if g == shopGroupItemShop {
			itemShop = id
		}
	}
	track("/apb.api.shop.ShopService/Buy", &pb.BuyRequest{ShopId: itemShop})
	track("/apb.api.explore.ExploreService/FinishExplore", &pb.FinishExploreRequest{ExploreId: 11})
	if cat.HistoryValue(&u, HistoryWeaponSkill) != 1 || cat.HistoryValue(&u, HistoryItemShopPurchases) != 1 ||
		cat.HistoryValue(&u, HistoryExchangeTrades) != 0 || cat.HistoryValue(&u, HistoryExploreGroup1) < 1 {
		t.Errorf("counted: %v", u.Ext.History)
	}
	items := cat.PlayHistory(&u)
	if len(items) != historyCount || items[0].HistoryItemId != 1 || items[historyCount-1].HistoryItemId != historyCount {
		t.Fatalf("%d history items", len(items))
	}
	if items[HistoryDaysLoggedIn-1].Count != int64(u.Login.TotalLoginCount) || items[HistoryCostumeTypes-1].Count == 0 {
		t.Errorf("from the save: %v", items)
	}
	for _, it := range items {
		t.Logf("history %d: %d", it.HistoryItemId, it.Count)
	}
}
