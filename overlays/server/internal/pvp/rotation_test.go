package pvp

import (
	"testing"
	"time"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

const testDay = 24 * 3600 * 1000

// mondayAt is Monday 00:00 GMT-8 of the week holding the given UTC date.
func mondayAt(y int, m time.Month, d int) int64 {
	return gametime.WeeklyVersion(time.Date(y, m, d, 12, 0, 0, 0, time.UTC).UnixMilli())
}

func testSeason(id int32, start, end int64, rankGroup int32) masterdata.EntityMPvpSeason {
	return masterdata.EntityMPvpSeason{
		PvpSeasonId: id, SeasonStartDatetime: start, SeasonEndDatetime: end,
		PvpGradeGroupId: 2, PvpSeasonRankRewardRankGroupId: rankGroup, PvpWeeklyRankRewardRankGroupId: 1,
	}
}

// With every season extended (Bunker's content patcher), the seasons with
// the latest season's tables take four-week turns, latest first.
func TestSeasonRotation(t *testing.T) {
	far := time.Date(2099, 1, 1, 0, 0, 0, 0, time.UTC).UnixMilli()
	s1, s2, s3 := mondayAt(2023, 8, 7), mondayAt(2023, 9, 4), mondayAt(2024, 2, 19)
	c := &Catalog{seasons: []masterdata.EntityMPvpSeason{
		testSeason(1, mondayAt(2022, 1, 3), far, 2), // other reward tables: never in turn
		testSeason(2, s1, far, 4),
		testSeason(3, s2, far, 4),
		testSeason(4, s3, far, 4),
		{PvpSeasonId: 5, SeasonStartDatetime: s3, SeasonEndDatetime: far, IsInvalid: true},
		testSeason(6, far, far+30*testDay, 4), // not started
	}}
	week := int64(weekMillis)
	for _, tc := range []struct {
		at   int64
		want int32
	}{
		{s3 + testDay, 4},
		{s3 + 4*week - 1, 4},
		{s3 + 4*week, 2},             // the turn changes on the weekly reset
		{s3 + 8*week + 3*testDay, 3}, // then the next, in order
		{s3 + 12*week, 4},            // and around again
		{s3 + 16*week, 2},
	} {
		if s, ok := c.Season(tc.at); !ok || s.PvpSeasonId != tc.want {
			t.Errorf("at %s: season %d %v, want %d", time.UnixMilli(tc.at).UTC(), s.PvpSeasonId, ok, tc.want)
		}
	}
	// A turn always lasts SeasonWeeks whole weeks.
	at := time.Date(2026, 11, 4, 12, 0, 0, 0, time.UTC).UnixMilli()
	cur, _ := c.Season(at)
	changes := 0
	for d := int64(0); d < 12*7; d++ {
		s, _ := c.Season(at + d*testDay)
		if s.PvpSeasonId != cur.PvpSeasonId {
			if gametime.WeeklyVersion(at+d*testDay) > at+d*testDay-testDay {
				changes++
			} else {
				t.Errorf("season changed mid-week on day %d", d)
			}
			cur = s
		}
	}
	if changes != 3 {
		t.Errorf("%d season changes in 12 weeks, want 3", changes)
	}
}

// With the game's own dates, seasons follow each other: no turns.
func TestSeasonOriginalDates(t *testing.T) {
	a, b := mondayAt(2023, 8, 7), mondayAt(2023, 8, 28)
	c := &Catalog{seasons: []masterdata.EntityMPvpSeason{
		testSeason(1, a, b, 4),
		testSeason(2, b, b+21*testDay, 4),
	}}
	for _, tc := range []struct {
		at   int64
		want int32
		open bool
	}{
		{a + testDay, 1, true},
		{b + testDay, 2, true},
		{b + 22*testDay, 0, false},
	} {
		s, ok := c.Season(tc.at)
		if ok != tc.open || s.PvpSeasonId != tc.want {
			t.Errorf("at %s: season %d %v, want %d %v", time.UnixMilli(tc.at).UTC(), s.PvpSeasonId, ok, tc.want, tc.open)
		}
	}
}

// With patched master data, the end of a turn ends the season: its final
// rank is due as a season reward, the week's result is kept and the next
// season starts from 0 points.
func TestSeasonTurnPaysFinalRank(t *testing.T) {
	c, u := realSave(t)
	now := time.Now().UnixMilli()
	first, ok := c.Season(now)
	if !ok {
		t.Skip("no Arena season open now: needs patched master data")
	}
	end := gametime.WeeklyVersion(now)
	for {
		end += weekMillis
		if s, _ := c.Season(end); s.PvpSeasonId != first.PvpSeasonId {
			break
		}
		if end > now+SeasonWeeks*weekMillis {
			t.Skip("this master data has a single Arena season: no turns")
		}
	}
	if _, _, ok := c.Sync(&u, now); !ok {
		t.Fatal("sync")
	}
	p := &u.Ext.Pvp
	p.Point = 6000
	want := c.Ladder(first.PvpSeasonId).Rank(p.Point)
	next, _, _ := c.Sync(&u, end+3600_000)
	if next.PvpSeasonId == first.PvpSeasonId || p.SeasonId != next.PvpSeasonId || p.Point != 0 {
		t.Fatalf("after the turn: season %d -> %d, points %d", first.PvpSeasonId, next.PvpSeasonId, p.Point)
	}
	if p.SeasonResult == nil || p.SeasonResult.SeasonId != first.PvpSeasonId || p.SeasonResult.FinalRank != want {
		t.Fatalf("season result %+v, want season %d rank %d", p.SeasonResult, first.PvpSeasonId, want)
	}
	reward, ok := c.PendingSeason(p)
	if !ok || len(reward.Rewards) == 0 {
		t.Fatalf("season reward %+v %v", reward, ok)
	}
	if len(p.Weekly) == 0 || p.Weekly[len(p.Weekly)-1].SeasonId != first.PvpSeasonId {
		t.Fatalf("last week's result not kept: %+v", p.Weekly)
	}
	t.Logf("season %d ended at rank %d: %v; season %d next", first.PvpSeasonId, want, reward.Rewards, next.PvpSeasonId)
}

// Two turns can end before the game claims (no Home visit in between): the
// earlier season's reward stays due with the later one, and both are paid.
func TestTwoSeasonEndsBeforeAClaimKeepBothRewards(t *testing.T) {
	c, u := realSave(t)
	now := time.Now().UnixMilli()
	first, ok := c.Season(now)
	if !ok {
		t.Skip("no Arena season open now: needs patched master data")
	}
	// The weekly resets where the next two turns start.
	var ends []int64
	for at := gametime.WeeklyVersion(now) + weekMillis; len(ends) < 2 && at < now+3*SeasonWeeks*weekMillis; at += weekMillis {
		before, _ := c.Season(at - 1)
		if s, _ := c.Season(at); s.PvpSeasonId != before.PvpSeasonId {
			ends = append(ends, at)
		}
	}
	if len(ends) < 2 {
		t.Skip("this master data has a single Arena season: no turns")
	}
	c.Sync(&u, now)
	p := &u.Ext.Pvp
	p.SeasonResult, p.EarlierSeasonResults = nil, nil // the test save's own ended season, if any
	p.Point = 6000
	second, _, _ := c.Sync(&u, ends[0]+3600_000)
	p.Point = 2500
	c.Sync(&u, ends[1]+3600_000)
	if p.SeasonResult == nil || p.SeasonResult.SeasonId != second.PvpSeasonId {
		t.Fatalf("latest season result %+v, want season %d", p.SeasonResult, second.PvpSeasonId)
	}
	earlier := c.PendingEarlierSeasons(p)
	if len(earlier) != 1 || earlier[0].Result.SeasonId != first.PvpSeasonId || earlier[0].Result.FinalRank != c.Ladder(first.PvpSeasonId).Rank(6000) || len(earlier[0].Rewards) == 0 {
		t.Fatalf("earlier season rewards %+v, want season %d's", earlier, first.PvpSeasonId)
	}
	latest, _ := c.PendingSeason(p)
	shown, rewards, ok := c.ClaimSeasons(p)
	if !ok || shown.Result.SeasonId != second.PvpSeasonId || len(rewards) != len(earlier[0].Rewards)+len(latest.Rewards) {
		t.Fatalf("claim: shown %+v, %d rewards, want season %d's report and both seasons' rewards", shown.Result, len(rewards), second.PvpSeasonId)
	}
	if _, rewards, ok := c.ClaimSeasons(p); ok || len(rewards) != 0 || p.RewardSeasonId != p.SeasonId {
		t.Fatalf("claimed again: %d rewards %v, reward season %d", len(rewards), ok, p.RewardSeasonId)
	}
}

// A season that ends mid-week (the first start after updating from a build
// that kept season 038) records that week; the week's own end must not add
// a second result for it, as the game keeps one per week.
func TestMidWeekSeasonChangeKeepsOneResultPerWeek(t *testing.T) {
	c, u := realSave(t)
	now := time.Now().UnixMilli()
	cur, ok := c.Season(now)
	if !ok {
		t.Skip("no Arena season open now: needs patched master data")
	}
	var other int32
	for _, s := range c.seasons {
		if !s.IsInvalid && s.PvpSeasonId != cur.PvpSeasonId && s.SeasonStartDatetime < now {
			other = s.PvpSeasonId
		}
	}
	week := gametime.WeeklyVersion(now)
	c.Sync(&u, now)
	p := &u.Ext.Pvp
	p.SeasonId, p.Point, p.WeekVersion, p.Weekly = other, 47, week, nil
	c.Sync(&u, now)
	if p.SeasonResult == nil || p.SeasonResult.SeasonId != other || len(p.Weekly) != 1 || p.Weekly[0].WeekVersion != week {
		t.Fatalf("mid-week change: result %+v, weekly %+v", p.SeasonResult, p.Weekly)
	}
	p.Point = 120 // defense battles during the week move it further
	c.Sync(&u, week+weekMillis+3600_000)
	seen := map[int64]bool{}
	for _, w := range p.Weekly {
		if seen[w.WeekVersion] {
			t.Fatalf("week %d recorded twice: %+v", w.WeekVersion, p.Weekly)
		}
		seen[w.WeekVersion] = true
	}
	if last := p.Weekly[len(p.Weekly)-1]; last.WeekVersion != week || last.SeasonId != cur.PvpSeasonId || last.FinalPoint == 0 {
		t.Fatalf("week's end: %+v", p.Weekly)
	}
}

// With the Original calendar at 7× speed the game clock gains a week at most
// daily resets. A visit after a jump past a season's end still records that
// season's final rank and the week the player was in, the game can claim
// them (that week is over), and they are paid once. Needs the original
// (unpatched) master data, whose seasons end.
func TestCalendarSpeedPaysSeasonEnd(t *testing.T) {
	c, u := realSave(t)
	// A season of three weeks or more, followed within a day by one of two
	// weeks or more, so a one-week jump past its end lands in the next.
	var season masterdata.EntityMPvpSeason
	for _, s := range c.seasons {
		if s.IsInvalid || s.SeasonEndDatetime >= patchedSeasonEnd || s.SeasonEndDatetime-s.SeasonStartDatetime < 21*testDay {
			continue
		}
		for _, n := range c.seasons {
			if !n.IsInvalid && n.SeasonStartDatetime >= s.SeasonEndDatetime && n.SeasonStartDatetime-s.SeasonEndDatetime < testDay &&
				n.SeasonEndDatetime-n.SeasonStartDatetime >= 14*testDay && s.SeasonStartDatetime > season.SeasonStartDatetime {
				season = s
			}
		}
	}
	if season.PvpSeasonId == 0 {
		t.Skip("needs the original master data, where seasons end")
	}
	// Loop 1 starts at launch, so the game data keeps its dates; the speed is
	// chosen ten days into the season, when real time and game time agree.
	real := season.SeasonStartDatetime + 10*testDay
	cal := &gametime.Calendar{Loop: 1, LoopStart: gametime.Launch, Speed: 7, SpeedSince: gametime.StartOfDay(real)}
	game := func(real int64) int64 { return real + cal.Shift(real) }

	p := &u.Ext.Pvp
	*p = store.PvpState{}
	if s, _, ok := c.Sync(&u, game(real)); !ok || s.PvpSeasonId != season.PvpSeasonId {
		t.Fatalf("start: season %d %v, want %d", s.PvpSeasonId, ok, season.PvpSeasonId)
	}
	// Visit once a real day until the game clock passes the season's end.
	jumps := 0
	for {
		p.Point = 1500
		next := real + testDay
		if game(next)-game(real) > testDay {
			jumps++
		}
		if game(next) >= season.SeasonEndDatetime {
			real = next
			break
		}
		real = next
		if s, _, _ := c.Sync(&u, game(real)); s.PvpSeasonId != season.PvpSeasonId {
			t.Fatalf("left season %d early, at %s", season.PvpSeasonId, time.UnixMilli(game(real)).UTC())
		}
	}
	if jumps == 0 {
		t.Fatal("7× speed never moved the game clock a week ahead")
	}
	lastWeek, want := p.WeekVersion, c.Ladder(season.PvpSeasonId).Rank(p.Point)
	now := game(real)
	next, _, ok := c.Sync(&u, now)
	if !ok || next.PvpSeasonId == season.PvpSeasonId || p.Point != 0 {
		t.Fatalf("after the end: season %d %v, points %d", next.PvpSeasonId, ok, p.Point)
	}
	if r := p.SeasonResult; r == nil || r.SeasonId != season.PvpSeasonId || r.FinalRank != want {
		t.Fatalf("season result %+v, want season %d rank %d", r, season.PvpSeasonId, want)
	}
	seen := map[int64]bool{}
	for _, w := range p.Weekly {
		if seen[w.WeekVersion] {
			t.Fatalf("week %d recorded twice: %+v", w.WeekVersion, p.Weekly)
		}
		seen[w.WeekVersion] = true
	}
	last := p.Weekly[len(p.Weekly)-1]
	if last.WeekVersion != lastWeek || last.SeasonId != season.PvpSeasonId || last.FinalPoint != 1500 {
		t.Fatalf("last week's result %+v, want week %d of season %d at 1500 points", last, lastWeek, season.PvpSeasonId)
	}
	// The game claims only when the latest result's week is a week old.
	if now-last.WeekVersion < weekMillis {
		t.Fatalf("the season's last week is not over at %s: the game would not claim", time.UnixMilli(now).UTC())
	}
	reward, ok := c.PendingSeason(p)
	if !ok || len(reward.Rewards) == 0 {
		t.Fatalf("season reward %+v %v", reward, ok)
	}
	pending := c.PendingWeekly(p)
	if len(pending) == 0 || pending[len(pending)-1].Result.WeekVersion != lastWeek {
		t.Fatalf("weekly rewards due: %+v", pending)
	}
	// The claim (ReceivePvpReward) marks both received; the next day's visit
	// owes nothing more for that season.
	p.SeasonResult, p.RewardSeasonId = nil, p.SeasonId
	p.RewardWeekVersion = pending[len(pending)-1].Result.WeekVersion
	c.Sync(&u, game(real+testDay))
	if _, ok := c.PendingSeason(p); ok {
		t.Fatal("season reward due again")
	}
	for _, w := range c.PendingWeekly(p) {
		if w.Result.SeasonId == season.PvpSeasonId {
			t.Fatalf("week of season %d due again: %+v", season.PvpSeasonId, w.Result)
		}
	}
	t.Logf("season %d ended at rank %d after %d one-week jumps: %v; then season %d", season.PvpSeasonId, want, jumps, reward.Rewards, next.PvpSeasonId)
}

// patchedSeasonEnd is where Bunker's patched seasons end (2099-01-01).
const patchedSeasonEnd int64 = 4070908800000
