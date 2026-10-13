package pvp

import (
	"context"
	"io"
	"lunar-tear/server/internal/gametime"
	"math/rand/v2"
	"os"
	"path/filepath"
	"testing"
	"time"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/store/sqlite"
	"lunar-tear/server/migrations"
)

// Runs against real game data: BUNKER_TEST_MASTER is a (patched) master data
// .bin.e and BUNKER_TEST_SAVE a game.db with one player. Skipped without them.
func realSave(t *testing.T) (*Catalog, store.UserState) {
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
	u, err := sqlite.New(db, time.Now).LoadUser(uid)
	if err != nil {
		t.Fatal(err)
	}
	return Current(), u
}

func TestLadder(t *testing.T) {
	c, _ := realSave(t)
	now := time.Now().UnixMilli()
	season, ok := c.Season(now)
	if !ok {
		t.Fatal("no season open")
	}
	l := c.Ladder(season.PvpSeasonId)
	again := load(c.cats).Ladder(season.PvpSeasonId)
	if l.cpus[123] != again.cpus[123] {
		t.Fatalf("ladder not the same each time: %+v vs %+v", l.cpus[123], again.cpus[123])
	}
	top := l.Ranked(1, 3, 0)
	if top[0].CPU.Point < top[1].CPU.Point || top[0].Rank != 1 {
		t.Fatalf("ranking out of order: %+v", top)
	}
	for _, cpu := range l.cpus[:50] {
		if cpu.Costumes[0] == 0 || cpu.Weapons[0] == 0 || cpu.Name == "" {
			t.Fatalf("computer player without a deck: %+v", cpu)
		}
	}
	// The player in the ranking: with the most points, first.
	if e := l.Ranked(1, 1, 1_000_000); !e[0].Player || l.Rank(1_000_000) != 1 {
		t.Fatalf("player not first with most points: %+v", e)
	}
	if l.Rank(0) < int32(l.Size()/2) {
		t.Fatalf("player with 0 points ranked %d of %d", l.Rank(0), l.Size())
	}
	t.Logf("season %d; top %s %d points, deck %v", season.PvpSeasonId, top[0].CPU.Name, top[0].CPU.Point, top[0].CPU.Costumes)
}

func TestBattle(t *testing.T) {
	c, u := realSave(t)
	now := time.Now().UnixMilli()
	season, ladder, ok := c.Sync(&u, now)
	if !ok {
		t.Fatal("no season open")
	}
	p := &u.Ext.Pvp
	if d := u.Decks[store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: 1}]; d.UserDeckCharacterUuid01 == "" || p.DefenseDeckNumber != 1 {
		t.Fatalf("no Arena deck made from quest deck 1: %+v, defense deck %d", d, p.DefenseDeckNumber)
	}
	if p.SeasonId != season.PvpSeasonId || c.BattlePointMilli(p, now) != c.MaxBattlePoint*1000 {
		t.Fatalf("new Arena state: %+v", p)
	}
	r := rand.New(rand.NewPCG(1, 2))
	c.Match(p, ladder, r)
	if len(p.Matching) != 3 {
		t.Fatalf("matching: %v", p.Matching)
	}
	cpu, _ := ladder.Get(p.Matching[2])
	if !c.Spend(p, c.BattleCost, now) || c.BattlePointMilli(p, now) != (c.MaxBattlePoint-c.BattleCost)*1000 {
		t.Fatalf("battle points after a battle: %d", c.BattlePointMilli(p, now))
	}
	// Battle points come back, one per RecoverySecond.
	if got := c.BattlePointMilli(p, now+int64(c.RecoverySecond)*1000); got != (c.MaxBattlePoint-c.BattleCost+1)*1000 {
		t.Fatalf("battle points after %ds: %d", c.RecoverySecond, got)
	}

	// The opponent deck is raised like the player's deck, within the game's limits.
	profile := c.ProfileOf(&u, store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: 1})
	deck := c.Deck(cpu, profile, Strength(cpu.Point, p.Point))
	if len(deck) != 3 {
		t.Fatalf("opponent deck has %d characters", len(deck))
	}
	for _, d := range deck {
		co, w := d.GetCostume(), d.GetMainWeapon()
		if co.Level < 1 || w.Level < 1 || len(w.WeaponSkill) == 0 || co.ActiveSkillLevel < 1 {
			t.Fatalf("opponent character: %+v / %+v", co, w)
		}
	}
	t.Logf("player deck %+v; opponent %s (%d points) lead %+v weapon %d lv %d", profile, cpu.Name, cpu.Point, deck[0].GetCostume(), deck[0].GetMainWeapon().WeaponId, deck[0].GetMainWeapon().Level)

	res := c.Finish(&u, season, ladder, cpu, true, now, r)
	if res.AfterPoint <= res.BeforePoint || res.AfterRank > res.BeforeRank || res.OneMatchRewardId == 0 || len(res.Rewards) == 0 {
		t.Fatalf("win: %+v", res)
	}
	if p.WinStreak != 1 || p.Season.AttackWins != 1 || len(p.AttackLog) != 1 || !p.AttackLog[0].Victory {
		t.Fatalf("after a win: %+v", p)
	}
	lost := c.Finish(&u, season, ladder, cpu, false, now+1, r)
	if lost.AfterPoint >= lost.BeforePoint || p.WinStreak != 0 {
		t.Fatalf("loss: %+v streak %d", lost, p.WinStreak)
	}
	t.Logf("win %+v; loss %d -> %d", res, lost.BeforePoint, lost.AfterPoint)
}

func TestWeekAndDefense(t *testing.T) {
	c, u := realSave(t)
	monday := time.Date(2026, 10, 5, 0, 0, 0, 0, gametime.Zone).UnixMilli() // weeks start Monday 00:00 GMT-8
	now := monday + 3*24*3600*1000                                          // a Thursday
	season, ladder, ok := c.Sync(&u, now)
	if !ok {
		t.Fatal("no season open")
	}
	p := &u.Ext.Pvp
	cpu, _ := ladder.Get(CpuIdBase + 10)
	c.Finish(&u, season, ladder, cpu, true, now, rand.New(rand.NewPCG(3, 4)))
	p.DefenseDeckNumber, p.DefenseChecked = 1, now
	won := p.Point

	// Twelve hours later: computer players have attacked the defense deck.
	later := now + 12*3600*1000
	c.Sync(&u, later)
	if len(p.DefenseLog) != defensePerSync || p.Season.DefenseWins+p.Season.DefenseLosses != defensePerSync {
		t.Fatalf("defense battles after 12h: %d logs, %+v", len(p.DefenseLog), p.Season)
	}
	if p.DefenseLog[0].Datetime > later || p.DefenseLog[0].Datetime < p.DefenseLog[len(p.DefenseLog)-1].Datetime {
		t.Fatalf("defense log order: %+v", p.DefenseLog)
	}
	t.Logf("points %d -> %d after defense: %+v", won, p.Point, p.Season)

	// Next week: last week's result is kept and its rewards are due once.
	nextWeek := monday + 7*24*3600*1000 + 3600*1000
	c.Sync(&u, nextWeek)
	if len(p.Weekly) != 1 || p.Weekly[0].WeekVersion != monday || p.Weekly[0].FinalPoint != p.Point {
		t.Fatalf("weekly results: %+v (points %d)", p.Weekly, p.Point)
	}
	pending := c.PendingWeekly(p)
	if len(pending) != 1 || len(pending[0].Rewards) == 0 || pending[0].RankGroup == 0 { // grade 1 has no weekly grade reward
		t.Fatalf("weekly rewards: %+v", pending)
	}
	p.RewardWeekVersion = pending[0].Result.WeekVersion
	if len(c.PendingWeekly(p)) != 0 {
		t.Fatal("weekly rewards due again")
	}
	t.Logf("week result %+v; rewards %+v", pending[0].Result, pending[0].Rewards)
}

func TestFriends(t *testing.T) {
	c, u := realSave(t)
	if c.Friend != (FriendLimits{Friends: 100, SendCheer: 100, ReceiveCheer: 100}) {
		t.Errorf("friend limits from m_config: %+v", c.Friend)
	}
	now := time.Now().UnixMilli()
	season, _ := c.Season(now)
	ladder := c.Ladder(season.PvpSeasonId)
	f := &u.Ext.Friends
	*f = store.FriendState{}
	day := int64(1_000_000)

	offered := c.Recommend(f, ladder, 1000, u.UserId, day)
	if len(offered) != recommendCount {
		t.Fatalf("%d recommended", len(offered))
	}
	if again := c.Recommend(f, ladder, 1000, u.UserId, day); again[0] != offered[0] {
		t.Error("recommendations change within a day")
	}
	a, b := offered[0].PlayerId, offered[1].PlayerId
	if !c.AddFriend(f, a) || c.AddFriend(f, a) || c.AddFriend(f, 12345) {
		t.Fatal("add friend: new once, not twice, not a real player id")
	}
	for _, cpu := range c.Recommend(f, ladder, 1000, u.UserId, day) {
		if cpu.PlayerId == a {
			t.Error("a friend is still recommended")
		}
	}
	c.AddFriend(f, b)

	// One cheer per friend per day, each way.
	if !c.Cheer(f, a, day) || c.Cheer(f, a, day) || c.Cheer(f, 999, day) {
		t.Fatal("cheer: once per friend, only friends")
	}
	if !c.ReceiveCheer(f, a, day) || c.ReceiveCheer(f, a, day) {
		t.Fatal("receive: once per friend")
	}
	if sent, got := CheerStatus(f, a, day); !sent || !got || SentToday(f, day) != 1 || ReceivedToday(f, day) != 1 {
		t.Fatalf("status today: %+v", f)
	}
	// The next day starts over; the total keeps counting.
	if SentToday(f, day+1) != 0 || !c.Cheer(f, a, day+1) || f.TotalSent != 2 {
		t.Fatalf("next day: %+v", f)
	}
	// The daily cheer limit.
	limits := c.Friend
	c.Friend.SendCheer = 1
	if c.Cheer(f, b, day+1) {
		t.Error("cheered past the daily limit")
	}
	c.Friend = limits
	// Removing and re-adding a friend the same day doesn't allow another cheer.
	RemoveFriend(f, a)
	if !c.AddFriend(f, a) || c.Cheer(f, a, day+1) {
		t.Error("cheered a re-added friend twice in a day")
	}
	RemoveFriend(f, a)
	if IsFriend(f, a) || c.Cheer(f, a, day+2) {
		t.Error("removed friend still a friend")
	}
}

func TestFriendCards(t *testing.T) {
	c, _ := realSave(t)
	season, _ := c.Season(time.Now().UnixMilli())
	ladder := c.Ladder(season.PvpSeasonId)
	levels, powers := map[int32]bool{}, map[int32]bool{}
	var lowSum, highSum, lowN, highN int64
	for i := int64(1); i <= int64(ladder.Size()); i++ {
		cpu, _ := ladder.Get(CpuIdBase + i)
		level, power := c.Card(cpu)
		if again, _ := c.Card(cpu); again != level {
			t.Fatalf("player %d card changes", cpu.PlayerId)
		}
		if level < 1 || level > c.maxUserLevel() || power < cardPowerLow*8/10 || power > cardPowerHigh*12/10 {
			t.Fatalf("player %d (%d points): level %d, power %d", cpu.PlayerId, cpu.Point, level, power)
		}
		levels[level], powers[power] = true, true
		switch {
		case cpu.Point < 5000:
			lowSum, lowN = lowSum+int64(level), lowN+1
		case cpu.Point > 40000:
			highSum, highN = highSum+int64(level), highN+1
		}
	}
	if len(levels) < 100 || len(powers) < ladder.Size()/2 {
		t.Errorf("cards too alike: %d levels, %d powers over %d players", len(levels), len(powers), ladder.Size())
	}
	if lowN == 0 || highN == 0 || lowSum/lowN >= highSum/highN {
		t.Errorf("average level below 5000 points %d, above 40000 %d", lowSum/max(1, lowN), highSum/max(1, highN))
	}
	t.Logf("levels: %d distinct; average %d (<5000 points) to %d (>40000); max level %d", len(levels), lowSum/max(1, lowN), highSum/max(1, highN), c.maxUserLevel())
}

// With the Original calendar seasons end: the final rank of the season the
// player took part in is paid once, and seasons skipped give nothing. Needs
// the original (unpatched) master data, whose seasons keep their dates.
func TestSeasonEndPaysFinalRank(t *testing.T) {
	c, u := realSave(t)
	first, ok := c.seasonById(202003)
	if after, open := c.Season(first.SeasonEndDatetime + 2*86400_000); !ok || !open || after.PvpSeasonId == 202003 {
		t.Skip("needs the original master data, where seasons end")
	}
	u.Ext.Pvp = store.PvpState{}
	at := first.SeasonStartDatetime + 3600_000
	if s, _, ok := c.Sync(&u, at); !ok || s.PvpSeasonId != 202003 {
		t.Fatalf("season at start: %d %v", s.PvpSeasonId, ok)
	}
	u.Ext.Pvp.Point = 1500
	if _, ok := c.PendingSeason(&u.Ext.Pvp); ok {
		t.Fatal("reward pending before the season ended")
	}
	next, _, ok := c.Sync(&u, first.SeasonEndDatetime+2*86400_000)
	if !ok || next.PvpSeasonId == 202003 {
		t.Fatalf("next season: %d %v", next.PvpSeasonId, ok)
	}
	p := &u.Ext.Pvp
	want := c.Ladder(202003).Rank(1500)
	if p.SeasonResult == nil || p.SeasonResult.SeasonId != 202003 || p.SeasonResult.FinalRank != want {
		t.Fatalf("season result %+v, want rank %d", p.SeasonResult, want)
	}
	if p.Point != 0 || p.RewardSeasonId == next.PvpSeasonId {
		t.Fatalf("new season state: points %d, reward season %d", p.Point, p.RewardSeasonId)
	}
	reward, ok := c.PendingSeason(p)
	if !ok || reward.RankGroup == 0 || len(reward.Rewards) == 0 {
		t.Fatalf("no season reward: %+v", reward)
	}
	// Paid, then a jump over several seasons without points pays nothing more.
	p.SeasonResult, p.RewardSeasonId = nil, p.SeasonId
	last, _ := c.seasonById(202010)
	if s, _, _ := c.Sync(&u, last.SeasonStartDatetime+3600_000); s.PvpSeasonId != 202010 || p.SeasonResult != nil {
		t.Fatalf("skipped seasons paid: %d %+v", s.PvpSeasonId, p.SeasonResult)
	}
}
