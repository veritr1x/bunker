package pvp

import (
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func TestRecoverBattlePoints(t *testing.T) {
	c := &Catalog{MaxBattlePoint: 30, RecoverySecond: 1000}
	now := int64(1_800_000_000_000)
	p := &store.PvpState{BattlePointMilli: 5000, BattlePointUpdated: now}
	c.Recover(p, model.EffectValueFixed, 10, 1, now) // item 4001: 10 points
	if got := c.BattlePointMilli(p, now); got != 15000 {
		t.Fatalf("after +10: %d", got)
	}
	c.Recover(p, model.EffectValuePermil, 500, 1, now) // item 4002: half the maximum
	if got := c.BattlePointMilli(p, now); got != 30000 {
		t.Fatalf("after +50%%: %d", got)
	}
	c.Recover(p, model.EffectValueFixed, 10, 2, now) // two at once, above the maximum
	if got := c.BattlePointMilli(p, now); got != 50000 {
		t.Fatalf("after 2x +10: %d", got)
	}
}
