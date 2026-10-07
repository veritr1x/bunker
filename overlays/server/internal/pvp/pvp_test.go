package pvp

import (
	"context"
	"io"
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
	monday := time.Date(2026, 10, 5, 0, 0, 0, 0, time.UTC).UnixMilli()
	now := monday + 3*24*3600*1000 // a Thursday
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
