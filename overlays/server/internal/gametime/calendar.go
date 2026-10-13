package gametime

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"sync/atomic"
	"time"
)

// Calendar is the Original calendar setting Pod Programs writes to
// calendar.json next to the save. The game data is built per loop with
// rotating content moved to start at LoopStart; the clock runs ahead of real
// time by JumpMillis plus whole weeks for faster speeds, one step at each
// daily reset.
type Calendar struct {
	Version    int     `json:"version"`
	Loop       int     `json:"loop"`
	LoopStart  int64   `json:"loopStart"`
	JumpMillis int64   `json:"jumpMillis"`
	Speed      float64 `json:"speed"`
	SpeedSince int64   `json:"speedSince"`
	Next       string  `json:"next,omitempty"`
	NextLoop   int     `json:"nextLoop,omitempty"`
}

// LoopWeeks is the length of one loop: global launch to the end of service.
const LoopWeeks = 144

var current atomic.Pointer[Calendar]

// SetCalendar switches the calendar clock on, or off when c is nil.
func SetCalendar(c *Calendar) {
	current.Store(c)
}

// CurrentCalendar returns the calendar in use, or nil when everything is open.
func CurrentCalendar() *Calendar {
	return current.Load()
}

// LoadCalendar reads calendar.json; a missing file means the calendar is off.
func LoadCalendar(path string) (*Calendar, error) {
	raw, err := os.ReadFile(path)
	if errors.Is(err, fs.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var c Calendar
	if err := json.Unmarshal(raw, &c); err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	if c.LoopStart == 0 || c.Loop < 1 {
		return nil, fmt.Errorf("read %s: no loop", path)
	}
	return &c, nil
}

// AutoWeeks is the whole weeks a faster speed has added by real time real:
// (speed-1)/7 of a week per daily reset since the speed was chosen.
func (c *Calendar) AutoWeeks(real int64) int64 {
	twice := int64(c.Speed*2 + 0.5)
	if twice <= 2 || c.SpeedSince == 0 {
		return 0
	}
	days := (StartOfDay(real) - c.SpeedSince) / dayMillis
	if days <= 0 {
		return 0
	}
	return days * (twice - 2) / 14
}

// Shift is how far the game clock runs ahead of real time.
func (c *Calendar) Shift(real int64) int64 {
	return c.JumpMillis + c.AutoWeeks(real)*weekMillis
}

// End is when the loop's game data runs out.
func (c *Calendar) End() int64 {
	return c.LoopStart + LoopWeeks*weekMillis
}

func calendarShift(real int64) int64 {
	if c := current.Load(); c != nil {
		return c.Shift(real)
	}
	return 0
}

// StartNextLoop swaps in the next loop's game data, built ahead by Pod
// Programs, once the game clock has passed the end of the loop. It returns
// the calendar to use; without next-loop data the old loop stays (nothing is
// open until Pod Programs builds the next one).
func StartNextLoop(path, master string, c *Calendar, real int64) (*Calendar, error) {
	if c == nil || real+c.Shift(real) < c.End() || c.Next == "" || c.NextLoop != c.Loop+1 {
		return c, nil
	}
	if _, err := os.Stat(c.Next); err != nil {
		return c, nil
	}
	next := *c
	next.Loop++
	next.LoopStart += LoopWeeks * weekMillis
	next.Next, next.NextLoop = "", 0
	raw, err := json.MarshalIndent(next, "", "  ")
	if err != nil {
		return c, err
	}
	if err := os.Rename(c.Next, master); err != nil {
		return c, err
	}
	// The client fetches game data again when its modification time changes.
	now := time.Now()
	_ = os.Chtimes(master, now, now)
	pending := path + ".tmp"
	if err := os.WriteFile(pending, raw, 0600); err != nil {
		return &next, err
	}
	return &next, os.Rename(pending, path)
}
