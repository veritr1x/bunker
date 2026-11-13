package pvp

import (
	"reflect"
	"strings"
	"testing"
	"time"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// pointsCatalog has one open season, 7, and the empty ladder cache Ladder
// fills; Sync needs nothing more of the catalogue.
func pointsCatalog(start, end int64) *Catalog {
	return &Catalog{
		seasons: []masterdata.EntityMPvpSeason{testSeason(7, start, end, 4)},
		ladders: map[int32]*Ladder{},
	}
}

func pointsNow() (start, now, far int64) {
	start = mondayAt(2026, 11, 2)
	return start, start + 3*testDay, time.Date(2099, 1, 1, 0, 0, 0, 0, time.UTC).UnixMilli()
}

func TestSetPointEntersSeason(t *testing.T) {
	start, now, far := pointsNow()
	c := pointsCatalog(start, far)
	u := &store.UserState{UserId: 1}
	season, rank, err := c.SetPoint(u, 52000, now)
	if err != nil {
		t.Fatal(err)
	}
	if season != 7 || rank != 1 {
		t.Fatalf("season %d rank %d, want 7 and 1", season, rank)
	}
	p := u.Ext.Pvp
	if p.Point != 52000 || p.SeasonId != 7 || p.MaxSeasonRank != 1 {
		t.Fatalf("point %d season %d max rank %d", p.Point, p.SeasonId, p.MaxSeasonRank)
	}
	// The next Arena visit keeps them.
	c.Sync(u, now+testDay)
	if u.Ext.Pvp.Point != 52000 {
		t.Fatalf("after the next visit: point %d, want 52000", u.Ext.Pvp.Point)
	}
}

func TestSetPointRefusesOutOfRange(t *testing.T) {
	start, now, far := pointsNow()
	c := pointsCatalog(start, far)
	for _, point := range []int32{-1, 52001} {
		u := &store.UserState{UserId: 1}
		before := u.Ext.Pvp.Clone()
		if _, _, err := c.SetPoint(u, point, now); err == nil {
			t.Errorf("%d: no error", point)
		}
		if !reflect.DeepEqual(u.Ext.Pvp, before) {
			t.Errorf("%d: the Arena state changed: %+v", point, u.Ext.Pvp)
		}
	}
}

func TestSetPointKeepsBetterRank(t *testing.T) {
	start, now, far := pointsNow()
	c := pointsCatalog(start, far)
	u := &store.UserState{UserId: 1}
	if _, _, err := c.SetPoint(u, 52000, now); err != nil {
		t.Fatal(err)
	}
	if _, _, err := c.SetPoint(u, 0, now); err != nil {
		t.Fatal(err)
	}
	if u.Ext.Pvp.Point != 0 || u.Ext.Pvp.MaxSeasonRank != 1 {
		t.Fatalf("point %d max rank %d, want 0 and 1", u.Ext.Pvp.Point, u.Ext.Pvp.MaxSeasonRank)
	}
}

func TestSetPointNoSeason(t *testing.T) {
	start, now, _ := pointsNow()
	c := pointsCatalog(start-30*testDay, start-testDay) // ended before now
	u := &store.UserState{UserId: 1}
	_, _, err := c.SetPoint(u, 100, now)
	if err == nil || !strings.Contains(err.Error(), "no Arena season is open") {
		t.Fatalf("err %v, want no Arena season is open", err)
	}
}
