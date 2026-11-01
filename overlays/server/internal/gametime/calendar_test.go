package gametime

import (
	"os"
	"path/filepath"
	"testing"
)

func TestCalendarSpeedStepsAtDailyReset(t *testing.T) {
	day := ms(t, "2026-10-13T08:00:00Z") // a game day start (00:00 GMT-8)
	c := &Calendar{Loop: 1, LoopStart: ms(t, "2026-10-07T02:00:00Z"), Speed: 7, SpeedSince: day}
	for _, step := range []struct {
		at    string
		weeks int64
	}{
		{"2026-10-13T09:00:00Z", 0},
		{"2026-10-14T07:59:59Z", 0},
		{"2026-10-14T08:00:00Z", 0}, // 6/7 of a week after one day
		{"2026-10-15T08:00:00Z", 1},
		{"2026-10-20T08:00:00Z", 6}, // seven days at 7x: six extra weeks
	} {
		if got := c.AutoWeeks(ms(t, step.at)); got != step.weeks {
			t.Errorf("7x at %s: %d weeks, want %d", step.at, got, step.weeks)
		}
	}
	c.Speed = 3.5
	if got := c.AutoWeeks(ms(t, "2026-10-27T08:00:00Z")); got != 5 { // 14 days * 2.5 / 7
		t.Errorf("3.5x after 14 days: %d weeks, want 5", got)
	}
	c.Speed = 1
	if got := c.Shift(ms(t, "2027-10-27T08:00:00Z")); got != 0 {
		t.Errorf("real time shifted by %d", got)
	}
}

func TestNowFollowsTheCalendar(t *testing.T) {
	defer SetCalendar(nil)
	SetCalendar(&Calendar{Loop: 1, LoopStart: 1, JumpMillis: 3 * dayMillis, Speed: 1})
	if d := NowMillis() - Now().Add(-3*24*3600e9).UnixMilli(); d < 3*dayMillis-1000 || d > 3*dayMillis+1000 {
		t.Fatalf("clock not three days ahead")
	}
	SetCalendar(nil)
	if calendarShift(NowMillis()) != 0 {
		t.Fatal("calendar off still shifts")
	}
}

func TestStartNextLoopFindsDataBesideTheMaster(t *testing.T) {
	dir := t.TempDir()
	master := filepath.Join(dir, "master.bin.e")
	os.WriteFile(master, []byte("loop1"), 0600)
	os.WriteFile(filepath.Join(dir, NextName), []byte("loop2"), 0600)
	path := filepath.Join(dir, "calendar.json")
	// iOS moves the app's folder on every install, so a stored full path goes stale.
	c := &Calendar{Loop: 1, LoopStart: ms(t, "2026-10-07T02:00:00Z"), Speed: 1, Next: "/old/container/calendar-next.bin.e", NextLoop: 2}
	got, err := StartNextLoop(path, master, c, c.End())
	if err != nil || got.Loop != 2 {
		t.Fatalf("next loop: %+v %v", got, err)
	}
	if raw, _ := os.ReadFile(master); string(raw) != "loop2" {
		t.Fatalf("master not swapped: %q", raw)
	}
}

func TestStartNextLoop(t *testing.T) {
	dir := t.TempDir()
	master := filepath.Join(dir, "master.bin.e")
	next := filepath.Join(dir, "next.bin.e")
	path := filepath.Join(dir, "calendar.json")
	os.WriteFile(master, []byte("loop1"), 0600)
	os.WriteFile(next, []byte("loop2"), 0600)
	start := ms(t, "2026-10-07T02:00:00Z")
	c := &Calendar{Loop: 1, LoopStart: start, Speed: 1, Next: next, NextLoop: 2}
	// Before the end nothing changes.
	got, err := StartNextLoop(path, master, c, c.End()-1)
	if err != nil || got != c {
		t.Fatalf("started early: %+v %v", got, err)
	}
	got, err = StartNextLoop(path, master, c, c.End())
	if err != nil || got.Loop != 2 || got.LoopStart != start+LoopWeeks*weekMillis || got.Next != "" {
		t.Fatalf("next loop: %+v %v", got, err)
	}
	if raw, _ := os.ReadFile(master); string(raw) != "loop2" {
		t.Fatalf("master not swapped: %q", raw)
	}
	saved, err := LoadCalendar(path)
	if err != nil || saved.Loop != 2 || saved.LoopStart != got.LoopStart {
		t.Fatalf("saved %+v %v", saved, err)
	}
	// Without next-loop data the loop stays.
	again, _ := StartNextLoop(path, master, saved, saved.End())
	if again != saved {
		t.Fatal("started a loop without its game data")
	}
	// The new loop opens when its first summons do, a whole day on.
	loopStart := saved.LoopStart
	moved, err := OpenAtFirstSummons(path, saved, loopStart+3600000)
	if err != nil || moved.JumpMillis != dayMillis {
		t.Fatalf("not moved to the first summons: %+v %v", moved, err)
	}
	if reread, _ := LoadCalendar(path); reread.JumpMillis != moved.JumpMillis {
		t.Fatalf("move not saved: %+v", reread)
	}
	if again, _ := OpenAtFirstSummons(path, moved, loopStart+3600000); again != moved {
		t.Fatal("moved twice")
	}
	if later, _ := OpenAtFirstSummons(path, saved, loopStart+FirstSummons); later != saved {
		t.Fatal("moved a clock already at the first summons")
	}
	if c, err := LoadCalendar(filepath.Join(dir, "missing.json")); c != nil || err != nil {
		t.Fatal("missing file should mean calendar off")
	}
}

// The original-dates view moves what the game sees back by the calendar's
// offset; it is off unless the calendar is on and the setting is.
func TestViewOffsetOnlyWithOriginalDates(t *testing.T) {
	defer SetCalendar(nil)
	SetCalendar(nil)
	if ViewOffset() != 0 {
		t.Fatal("offset with the calendar off")
	}
	c := &Calendar{Loop: 1, LoopStart: Launch + 100*weekMillis}
	SetCalendar(c)
	if ViewOffset() != 0 {
		t.Fatal("offset with the setting off")
	}
	c.OriginalDates = true
	if ViewOffset() != 100*weekMillis {
		t.Fatalf("offset %d", ViewOffset())
	}
	SetCalendar(&Calendar{Loop: 2, LoopStart: Launch + 244*weekMillis, OriginalDates: true})
	if ViewOffset() != 244*weekMillis {
		t.Fatalf("loop 2 offset %d", ViewOffset())
	}
}

func TestToViewKeepsSentinels(t *testing.T) {
	defer SetCalendar(nil)
	SetCalendar(&Calendar{Loop: 1, LoopStart: Launch + 100*weekMillis, OriginalDates: true})
	real := Launch + 120*weekMillis
	if got := ToView(real); got != real-100*weekMillis {
		t.Fatalf("real time %d -> %d", real, got)
	}
	for _, v := range []int64{0, 4070908800000, 253402300799000, 946684799999} {
		if ToView(v) != v {
			t.Fatalf("sentinel %d moved", v)
		}
	}
}
