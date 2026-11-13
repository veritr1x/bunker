package lunarbase

import (
	"errors"

	"lunar-tear/server/internal/pvp"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
)

// Bunker: Pod Programs › Players › Arena points (android_arena.py).
// "set_arena_points" gives a player arena_points Arena points in the season
// open now, through the server's own Arena sync (pvp.Catalog.SetPoint), so
// the points survive the next Arena visit. It answers with the points, the
// season and the rank.

type arenaPointsData struct {
	Point    int32 `json:"point"`
	SeasonID int32 `json:"season_id"`
	Rank     int32 `json:"rank"`
}

func runSetArenaPoints(req *request) (int, error) {
	if req.ArenaPoints == nil {
		return 0, errors.New("arena_points required")
	}
	// The running server's catalogue when there is one, as arena_matching.
	c := pvp.Current()
	if c == nil {
		if req.MasterDataPath == "" {
			return 0, errors.New("master_data_path required for set_arena_points")
		}
		h, err := runtime.NewHolder(req.MasterDataPath)
		if err != nil {
			return 0, err
		}
		c = pvp.CatalogFor(h.Get())
	}
	db, st, err := openDB(req.DBPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	var out arenaPointsData
	var setErr error
	if _, err := st.UpdateUser(req.UserID, func(u *store.UserState) {
		out.SeasonID, out.Rank, setErr = c.SetPoint(u, *req.ArenaPoints, giftNow())
		out.Point = u.Ext.Pvp.Point
	}); err != nil {
		return 0, err
	}
	if setErr != nil {
		return 0, setErr
	}
	readData = out
	return 1, nil
}
