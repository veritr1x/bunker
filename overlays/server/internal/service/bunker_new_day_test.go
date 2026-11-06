package service

import (
	"os"
	"path/filepath"
	"strconv"
	"testing"
	"time"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
)

// Start a new day resets dailies only: shop stock on a period of several days
// keeps counting whole days, while a daily period starts over at the press.
func TestMultiDayShopPeriodIgnoresPress(t *testing.T) {
	at := func(h int) int64 { return time.Date(2025, 3, 12, h, 0, 0, 0, gametime.Zone).UnixMilli() }
	three := masterdata.ShopStockReset{Type: masterdata.ShopAutoResetDaily, Period: 3}
	daily := masterdata.ShopStockReset{Type: masterdata.ShopAutoResetDaily, Period: 1}
	before, _ := shopStockPeriodStart(three, at(16))
	path := filepath.Join(t.TempDir(), "day-start.json")
	if err := os.WriteFile(path, []byte(`{"pressedRealMillis": `+strconv.FormatInt(at(15), 10)+`}`), 0o600); err != nil {
		t.Fatal(err)
	}
	gametime.SetDayStartPath(path)
	t.Cleanup(func() { gametime.SetDayStartPath("") })
	if got, _ := shopStockPeriodStart(three, at(16)); got != before {
		t.Fatalf("3-day period moved by a press: %d -> %d", before, got)
	}
	if got, _ := shopStockPeriodStart(daily, at(16)); got != at(15) {
		t.Fatalf("daily period starts at the press: %v", time.UnixMilli(got).In(gametime.Zone))
	}
}
