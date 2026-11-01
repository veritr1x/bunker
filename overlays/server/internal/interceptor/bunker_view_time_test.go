package interceptor

import (
	"testing"

	"lunar-tear/server/internal/gametime"
)

const week = int64(7 * 24 * 3600 * 1000)

func near(a, b int64) bool { return a-b < 1000 && b-a < 1000 }

// The time trailer is the game's clock: in the original-dates view it runs
// the calendar's offset behind.
func TestTrailerShowsTheViewClock(t *testing.T) {
	defer gametime.SetCalendar(nil)
	c := &gametime.Calendar{Loop: 1, LoopStart: gametime.Launch + 100*week}
	gametime.SetCalendar(c)
	if !near(viewNowMillis(), gametime.NowMillis()) {
		t.Fatal("moved with the setting off")
	}
	c.OriginalDates = true
	if !near(viewNowMillis(), gametime.NowMillis()-100*week) {
		t.Fatalf("view clock %d, now %d", viewNowMillis(), gametime.NowMillis())
	}
}
