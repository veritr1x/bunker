package pvp

import (
	"errors"
	"fmt"

	"lunar-tear/server/internal/store"
)

// Bunker: Pod Programs › Players › Arena points (lunarbase set_arena_points).

// MaxPlayerPoint is the most Arena points a player can be given: the top
// computer player's, so rank 1.
const MaxPlayerPoint int32 = topPoint

// SetPoint gives the player point Arena points in the season open at now.
// The Arena sync runs first, so a save that has never been in this season
// enters it and the points survive the next Arena visit. The best season
// rank follows when the new rank is better. Out-of-range points change
// nothing. The points count for the week's and season's rewards like any
// others.
func (c *Catalog) SetPoint(u *store.UserState, point int32, now int64) (seasonId, rank int32, err error) {
	if point < 0 || point > MaxPlayerPoint {
		return 0, 0, fmt.Errorf("arena points must be 0–%d", MaxPlayerPoint)
	}
	season, ladder, ok := c.Sync(u, now)
	if !ok {
		return 0, 0, errors.New("no Arena season is open")
	}
	p := &u.Ext.Pvp
	p.Point = point
	rank = ladder.Rank(point)
	if p.MaxSeasonRank == 0 || rank < p.MaxSeasonRank {
		p.MaxSeasonRank = rank
	}
	p.LatestVersion = now
	return season.PvpSeasonId, rank, nil
}
