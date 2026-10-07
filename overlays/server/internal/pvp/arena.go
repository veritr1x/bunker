package pvp

import (
	"math/rand/v2"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

const (
	logLimit       = 20
	weeklyLimit    = 10
	defenseEvery   = 90 * 60 * 1000 // a computer player attacks the defense deck every 90 minutes
	defensePerSync = 8              // at most this many while the player was away
)

// Sync brings the player's Arena up to now: a new season starts from 0
// points, a new week records last week's result, defense battles since the
// last visit are played out. ok is false when no season is open.
func (c *Catalog) Sync(u *store.UserState, now int64) (season masterdata.EntityMPvpSeason, ladder *Ladder, ok bool) {
	season, ok = c.Season(now)
	if !ok {
		return season, nil, false
	}
	p := &u.Ext.Pvp
	ladder = c.Ladder(season.PvpSeasonId)
	if p.SeasonId != season.PvpSeasonId {
		if p.SeasonId != 0 {
			c.closeWeek(p, ladder)
		}
		*p = store.PvpState{
			SeasonId: season.PvpSeasonId, BattlePointMilli: p.BattlePointMilli, BattlePointUpdated: p.BattlePointUpdated,
			DefenseDeckNumber: p.DefenseDeckNumber, DefenseDeckPower: p.DefenseDeckPower,
			Weekly: p.Weekly, RewardWeekVersion: p.RewardWeekVersion, RewardSeasonId: p.RewardSeasonId,
		}
		p.LatestVersion = now
	}
	if p.BattlePointUpdated == 0 {
		p.BattlePointMilli, p.BattlePointUpdated = c.MaxBattlePoint*1000, now
	}
	ensureArenaDeck(u, now)
	c.simulateDefense(u, ladder, now)
	week := gametime.WeeklyVersion(now) // Monday 00:00 UTC
	if p.WeekVersion == 0 {
		p.WeekVersion = week
	} else if p.WeekVersion < week {
		c.closeWeek(p, ladder)
		p.WeekVersion = week
		p.LatestVersion = now
	}
	// There are no season rank rewards (Bunker's seasons never end).
	p.RewardSeasonId = season.PvpSeasonId
	if rank := ladder.Rank(p.Point); p.MaxSeasonRank == 0 || rank < p.MaxSeasonRank {
		p.MaxSeasonRank = rank
	}
	return season, ladder, true
}

// ensureArenaDeck gives a player without Arena decks one, a copy of quest
// deck 1, and makes it the defense deck. The game's opponent screen hangs
// when there is no Arena deck to select.
func ensureArenaDeck(u *store.UserState, now int64) {
	for k, d := range u.Decks {
		if k.DeckType == model.DeckTypePvp && d.UserDeckCharacterUuid01 != "" {
			return
		}
	}
	slots := store.ReadDeckSlots(u, model.DeckTypeQuest, 1)
	if slots == nil {
		return
	}
	store.ApplyDeckReplacement(u, model.DeckTypePvp, 1, slots, now)
	from, to := store.DeckKey{DeckType: model.DeckTypeQuest, UserDeckNumber: 1}, store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: 1}
	deck := u.Decks[to]
	deck.Name, deck.Power = u.Decks[from].Name, u.Decks[from].Power
	u.Decks[to] = deck
	p := &u.Ext.Pvp
	if p.DefenseDeckNumber == 0 {
		p.DefenseDeckNumber, p.DefenseDeckPower, p.DefenseChecked = 1, deck.Power, now
	}
}

// closeWeek records the week's result if the player took part.
func (c *Catalog) closeWeek(p *store.PvpState, ladder *Ladder) {
	played := p.Point > 0
	for _, l := range p.AttackLog {
		if l.Datetime >= p.WeekVersion {
			played = true
		}
	}
	if !played {
		return
	}
	group := int32(1)
	if s, ok := c.seasonById(p.SeasonId); ok {
		group = c.GroupId(s)
	}
	p.Weekly = append(p.Weekly, store.PvpWeeklyResult{
		WeekVersion: p.WeekVersion, SeasonId: p.SeasonId, GroupId: group,
		FinalPoint: p.Point, FinalRank: ladder.Rank(p.Point),
	})
	if len(p.Weekly) > weeklyLimit {
		p.Weekly = p.Weekly[len(p.Weekly)-weeklyLimit:]
	}
}

// BattlePointMilli is the player's battle points now, in thousandths.
func (c *Catalog) BattlePointMilli(p *store.PvpState, now int64) int32 {
	full := c.MaxBattlePoint * 1000
	if p.BattlePointUpdated == 0 {
		return full
	}
	if p.BattlePointMilli >= full {
		return p.BattlePointMilli
	}
	gained := (now - p.BattlePointUpdated) / int64(c.RecoverySecond)
	return int32(min(int64(full), int64(p.BattlePointMilli)+gained))
}

// Spend takes battle points; false (and nothing taken) if there are too few.
func (c *Catalog) Spend(p *store.PvpState, cost int32, now int64) bool {
	cur := c.BattlePointMilli(p, now)
	if cur < cost*1000 {
		return false
	}
	p.BattlePointMilli = cur - cost*1000
	p.BattlePointUpdated = now
	p.LatestVersion = now
	return true
}

// Match offers three computer players: one with fewer points, one about even, one with more.
func (c *Catalog) Match(p *store.PvpState, ladder *Ladder, r *rand.Rand) {
	skip := map[int64]bool{}
	var out []int64
	for _, offset := range []int32{-(300 + r.Int32N(1200)), r.Int32N(600) - 300, 300 + r.Int32N(1200)} {
		cpu, ok := ladder.Near(max(0, p.Point+offset), skip, r)
		if !ok {
			continue
		}
		skip[cpu.PlayerId] = true
		out = append(out, cpu.PlayerId)
	}
	p.Matching = out
}

func clamp(v, lo, hi int32) int32 { return max(lo, min(hi, v)) }

// AttackDelta is the player's point change for a battle they started.
func AttackDelta(me, opp int32, win bool) int32 {
	diff := opp - me
	if win {
		return clamp(100+diff/20, 40, 200)
	}
	return -clamp(60-diff/40, 20, 100)
}

// DefenseDelta is the player's point change when a computer player attacks them.
func DefenseDelta(me, attacker int32, defended bool) int32 {
	diff := attacker - me
	if defended {
		return clamp(30+diff/60, 10, 60)
	}
	return -clamp(40-diff/80, 15, 70)
}

func pushLog(logs []store.PvpLog, l store.PvpLog) []store.PvpLog {
	logs = append([]store.PvpLog{l}, logs...)
	if len(logs) > logLimit {
		logs = logs[:logLimit]
	}
	return logs
}

// simulateDefense plays the computer players' attacks on the defense deck
// since the last visit. The defense deck holds better against weaker attackers.
func (c *Catalog) simulateDefense(u *store.UserState, ladder *Ladder, now int64) {
	p := &u.Ext.Pvp
	if p.DefenseDeckNumber == 0 || p.DefenseChecked == 0 {
		p.DefenseChecked = now
		return
	}
	n := (now - p.DefenseChecked) / defenseEvery
	if n <= 0 {
		return
	}
	start := p.DefenseChecked
	if n > defensePerSync {
		start = now - defensePerSync*defenseEvery
		n = defensePerSync
	}
	r := rand.New(rand.NewPCG(uint64(u.UserId), uint64(p.DefenseChecked)))
	for i := int64(1); i <= n; i++ {
		attacker, ok := ladder.Near(max(0, p.Point+r.Int32N(4000)-2000), nil, r)
		if !ok {
			break
		}
		odds := 0.55 - (Strength(attacker.Point, p.Point)-1)*1.5
		defended := r.Float64() < max(0.15, min(0.85, odds))
		delta := DefenseDelta(p.Point, attacker.Point, defended)
		p.Point = max(0, p.Point+delta)
		if defended {
			p.Season.DefenseWins++
		} else {
			p.Season.DefenseLosses++
		}
		p.Season.DefensePoint += delta
		p.DefenseLog = pushLog(p.DefenseLog, store.PvpLog{
			PlayerId: attacker.PlayerId, Point: attacker.Point, Victory: defended,
			Datetime: start + i*defenseEvery, Fluctuation: delta,
		})
	}
	p.DefenseChecked = start + n*defenseEvery
	p.LatestVersion = now
}

// Result is the outcome of a battle the player started.
type Result struct {
	BeforePoint, BeforeRank, AfterPoint, AfterRank int32
	OneMatchRewardId, GradeGroupId                 int32
	Rewards                                        []Reward
}

// Finish records a battle against a computer player and picks the win reward
// of the player's grade.
func (c *Catalog) Finish(u *store.UserState, season masterdata.EntityMPvpSeason, ladder *Ladder, cpu CPU, win bool, now int64, r *rand.Rand) Result {
	p := &u.Ext.Pvp
	res := Result{BeforePoint: p.Point, BeforeRank: ladder.Rank(p.Point), GradeGroupId: season.PvpGradeGroupId}
	delta := AttackDelta(p.Point, cpu.Point, win)
	if win {
		grade := c.Grade(season, p.Point)
		res.OneMatchRewardId = c.pickOneMatch(grade.PvpGradeOneMatchRewardGroupId, r)
		res.Rewards = c.rewardList(c.oneMatchIds[res.OneMatchRewardId])
		p.WinStreak++
		p.Season.AttackWins++
	} else {
		p.WinStreak = 0
		p.Season.AttackLosses++
	}
	p.WinStreakUpdated = now
	p.Point = max(0, p.Point+delta)
	p.Season.AttackPoint += delta
	p.AttackLog = pushLog(p.AttackLog, store.PvpLog{PlayerId: cpu.PlayerId, Point: cpu.Point, Victory: win, Datetime: now, Fluctuation: delta})
	p.Opponent = 0
	p.LatestVersion = now
	res.AfterPoint, res.AfterRank = p.Point, ladder.Rank(p.Point)
	if p.MaxSeasonRank == 0 || res.AfterRank < p.MaxSeasonRank {
		p.MaxSeasonRank = res.AfterRank
	}
	return res
}

func (c *Catalog) pickOneMatch(group int32, r *rand.Rand) int32 {
	rows := c.oneMatch[group]
	var total int32
	for _, x := range rows {
		total += x.Weight
	}
	if total <= 0 {
		return 0
	}
	roll := r.Int32N(total)
	for _, x := range rows {
		if roll < x.Weight {
			return x.PvpGradeOneMatchRewardId
		}
		roll -= x.Weight
	}
	return 0
}

// WeeklyRewards are the rewards for a past week: by the grade reached and by rank.
type WeeklyRewards struct {
	Result                      store.PvpWeeklyResult
	GradeRewardGroup, RankGroup int32
	Rewards                     []Reward
}

// PendingWeekly lists the weeks whose rewards the player has not received, oldest first.
func (c *Catalog) PendingWeekly(p *store.PvpState) []WeeklyRewards {
	var out []WeeklyRewards
	for _, w := range p.Weekly {
		if w.WeekVersion <= p.RewardWeekVersion {
			continue
		}
		season, ok := c.seasonById(w.SeasonId)
		if !ok {
			continue
		}
		wr := WeeklyRewards{Result: w}
		wr.GradeRewardGroup = c.Grade(season, w.FinalPoint).PvpGradeWeeklyRewardGroupId
		wr.RankGroup = c.weeklyRankGroup(season, w.FinalRank)
		wr.Rewards = append(c.rewardList(c.weeklyGrade[wr.GradeRewardGroup]), c.rewardList(c.weeklyRank[wr.RankGroup])...)
		out = append(out, wr)
	}
	return out
}
