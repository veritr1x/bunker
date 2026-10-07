package missions

import (
	"sort"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

type Reward struct {
	PossessionType int32
	PossessionId   int32
	Count          int32
}

func (cat *Catalog) grant(u *store.UserState, g *store.PossessionGranter, r Reward, now int64) {
	if model.PossessionType(r.PossessionType) == model.PossessionTypeMissionPassPoint {
		// The possession id is the mission pass.
		p := u.Ext.MissionPass[r.PossessionId]
		p.MissionPassId = r.PossessionId
		p.Point += r.Count
		p.LatestVersion = now
		u.Ext.MissionPass[r.PossessionId] = p
		return
	}
	g.GrantFull(u, model.PossessionType(r.PossessionType), r.PossessionId, r.Count, now)
}

// ReceiveMissions pays the rewards of cleared missions and marks them received.
func (cat *Catalog) ReceiveMissions(u *store.UserState, g *store.PossessionGranter, ids []int32, now int64) []Reward {
	u.Ext.EnsureMaps()
	var out []Reward
	for _, id := range ids {
		m, ok := cat.ById[id]
		rec := u.Missions[id]
		if !ok || rec.MissionProgressStatusType != StatusClear {
			continue
		}
		for _, r := range cat.Rewards[m.MissionRewardId] {
			reward := Reward{r.PossessionType, r.PossessionId, r.Count}
			cat.grant(u, g, reward, now)
			out = append(out, reward)
		}
		rec.MissionProgressStatusType = StatusRewardReceived
		rec.LatestVersion = now
		u.Missions[id] = rec
	}
	// Receiving can complete "Complete N missions" and "Clear all daily missions".
	cat.trackCompletion(u, now, startOfDay(now))
	return out
}

type passRow struct {
	Level, SortOrder int32
	IsPremium        bool
	Reward
}

// PassLevel is the level a mission pass has reached with its points.
func (cat *Catalog) PassLevel(passId, points int32) int32 {
	levels := cat.PassLevels[cat.Passes[passId].MissionPassLevelGroupId]
	var level int32
	for _, l := range levels {
		if points >= l.NecessaryPoint && l.Level > level {
			level = l.Level
		}
	}
	return level
}

// ReceivePass pays a mission pass's rewards for every level reached and not yet
// received. Premium rewards need the pass's premium item.
func (cat *Catalog) ReceivePass(u *store.UserState, g *store.PossessionGranter, passId int32, now int64) []Reward {
	u.Ext.EnsureMaps()
	pass, ok := cat.Passes[passId]
	if !ok {
		return nil
	}
	state, ok := u.Ext.MissionPass[passId]
	if !ok {
		return nil // no points yet
	}
	level := cat.PassLevel(passId, state.Point)
	premium := pass.PremiumItemId != 0 && u.PremiumItems[pass.PremiumItemId] != 0
	var rows []passRow
	for _, r := range cat.PassRewards[pass.MissionPassRewardGroupId] {
		rows = append(rows, passRow{r.Level, r.SortOrder, r.IsPremium, Reward{r.PossessionType, r.PossessionId, r.Count}})
	}
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].Level != rows[j].Level {
			return rows[i].Level < rows[j].Level
		}
		return rows[i].SortOrder < rows[j].SortOrder
	})
	var out []Reward
	for _, r := range rows {
		if r.Level > level {
			break
		}
		if r.IsPremium {
			if !premium || r.Level <= state.PremiumRewardReceivedLevel {
				continue
			}
		} else if r.Level <= state.NoPremiumRewardReceivedLevel {
			continue
		}
		cat.grant(u, g, r.Reward, now)
		out = append(out, r.Reward)
	}
	state.NoPremiumRewardReceivedLevel = max(state.NoPremiumRewardReceivedLevel, level)
	if premium {
		state.PremiumRewardReceivedLevel = max(state.PremiumRewardReceivedLevel, level)
	}
	state.LatestVersion = now
	u.Ext.MissionPass[passId] = state
	return out
}

// ReceiveEndedPasses pays what is left on passes that have ended. It returns
// the last pass that paid anything, or 0.
func (cat *Catalog) ReceiveEndedPasses(u *store.UserState, g *store.PossessionGranter, now int64) int32 {
	var last int32
	ids := make([]int32, 0, len(u.Ext.MissionPass))
	for id := range u.Ext.MissionPass {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	for _, id := range ids {
		if p, ok := cat.Passes[id]; ok && p.EndDatetime != 0 && p.EndDatetime <= now {
			if len(cat.ReceivePass(u, g, id, now)) > 0 {
				last = id
			}
		}
	}
	return last
}
