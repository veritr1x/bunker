package pvp

// Pod Programs › Deck Builder reads the player's current matching list to
// build a deck against one of them. Read-only: nothing here changes the
// player's state.

import (
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
)

// Opponent is a computer player as Deck Builder shows it.
type Opponent struct {
	PlayerId int64    `json:"id"`
	Name     string   `json:"name"`
	Point    int32    `json:"points"`
	Costumes [3]int32 `json:"costumes"` // left, middle, right
	Weapons  [3]int32 `json:"weapons"`
}

// CatalogFor is the catalog for master data loaded outside the running server
// (the save editor's own runtime.Holder).
func CatalogFor(cats *runtime.Catalogs) *Catalog {
	cacheMu.Lock()
	defer cacheMu.Unlock()
	if c, ok := cache[cats]; ok {
		return c
	}
	c := load(cats)
	cache[cats] = c
	return c
}

// Opponents are the computer players on the player's matching list now, in
// the order the game lists them.
func (c *Catalog) Opponents(u *store.UserState, now int64) []Opponent {
	season, ok := c.Season(now)
	if !ok || u.Ext.Pvp.SeasonId != season.PvpSeasonId {
		return nil
	}
	l := c.Ladder(season.PvpSeasonId)
	var out []Opponent
	for _, id := range u.Ext.Pvp.Matching {
		cpu, ok := l.Get(id)
		if !ok {
			continue
		}
		cpu = c.Dress(l, cpu, u) // the deck it fields (decktable.go)
		out = append(out, Opponent{PlayerId: cpu.PlayerId, Name: cpu.Name, Point: cpu.Point, Costumes: cpu.Costumes, Weapons: cpu.Weapons})
	}
	return out
}
