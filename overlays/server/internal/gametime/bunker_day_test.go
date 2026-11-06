package gametime

import (
	"os"
	"path/filepath"
	"strconv"
	"testing"
	"time"
)

// pressAt writes day-start.json as Pod Programs does for a press at real ms.
func pressAt(t *testing.T, real int64) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "day-start.json")
	if err := os.WriteFile(path, []byte(`{"pressedRealMillis": `+strconv.FormatInt(real, 10)+`}`), 0o600); err != nil {
		t.Fatal(err)
	}
	SetDayStartPath(path)
	t.Cleanup(func() { SetDayStartPath("") })
}

func init() { dayStartRecheck = 0 }

// at is a game time on 2025-03-12 (GMT-8) at hour h.
func at(h int) int64 { return time.Date(2025, 3, 12, h, 0, 0, 0, Zone).UnixMilli() }

func TestNewDayResetsDailies(t *testing.T) {
	pressAt(t, at(15))
	if got := StartOfDay(at(16)); got != at(15) {
		t.Fatalf("after the press the day starts at the press: %v", time.UnixMilli(got).In(Zone))
	}
	if got := StartOfDay(at(13)); got != at(0) {
		t.Fatalf("before the press the day is as before: %v", time.UnixMilli(got).In(Zone))
	}
	if got := BaseStartOfDay(at(16)); got != at(0) {
		t.Fatalf("BaseStartOfDay ignores the press: %v", time.UnixMilli(got).In(Zone))
	}
	if !NewDayPausesBonus(at(16)) {
		t.Fatal("the bonus is paused on the day of a press")
	}
}

func TestNewDayEndsAtTheNextRealDay(t *testing.T) {
	pressAt(t, at(15))
	next := at(25) // 01:00 the next day
	if got := StartOfDay(next); got != at(24) {
		t.Fatalf("next day starts as usual: %v", time.UnixMilli(got).In(Zone))
	}
	if NewDayPausesBonus(next) {
		t.Fatal("the bonus is back the next day")
	}
}

func TestWeeklyUntouched(t *testing.T) {
	before := WeeklyVersion(at(16))
	pressAt(t, at(15))
	if WeeklyVersion(at(16)) != before {
		t.Fatal("a press moved the week")
	}
}

func TestNoFileNoChange(t *testing.T) {
	SetDayStartPath(filepath.Join(t.TempDir(), "missing.json"))
	t.Cleanup(func() { SetDayStartPath("") })
	if StartOfDay(at(16)) != at(0) || NewDayPausesBonus(at(16)) {
		t.Fatal("no file changed the day")
	}
}

func TestPressWithCalendarShift(t *testing.T) {
	saved := CurrentCalendar()
	t.Cleanup(func() { SetCalendar(saved) })
	year := int64(365 * dayMillis)
	SetCalendar(&Calendar{Version: 1, Loop: 1, LoopStart: Launch, JumpMillis: year, Speed: 1})
	real := at(15) - year // pressed at real time, shown a year later in game time
	pressAt(t, real)
	if got := StartOfDay(at(16)); got != at(15) {
		t.Fatalf("the press maps into game time: %v", time.UnixMilli(got).In(Zone))
	}
}
