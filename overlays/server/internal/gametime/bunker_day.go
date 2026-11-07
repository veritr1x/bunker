package gametime

// Pod Programs › Content › Start a new day: day-start.json in the save folder
// holds when it was pressed (real time). From then until the next game day,
// the day starts at the press, so everything daily (quest plays, missions,
// shop stock and lineups, free summons, cheers, the login bonus) starts over.
// Weekly keys and the calendar don't move. The file is read like mods.json:
// again only when it changes, and at most once a second.

import (
	"encoding/json"
	"os"
	"sync"
	"time"
)

var dayStart struct {
	sync.Mutex
	path    string
	modTime time.Time
	size    int64
	pressed int64 // real ms, 0 for none
	checked time.Time
}

// dayStartRecheck is how often the file is looked at again. Tests set 0.
var dayStartRecheck = time.Second

// SetDayStartPath names day-start.json; "" means no press.
func SetDayStartPath(path string) {
	dayStart.Lock()
	dayStart.path, dayStart.modTime, dayStart.size, dayStart.pressed, dayStart.checked = path, time.Time{}, -1, 0, time.Time{}
	dayStart.Unlock()
}

func pressedReal() int64 {
	dayStart.Lock()
	defer dayStart.Unlock()
	if dayStart.path == "" {
		return 0
	}
	now := time.Now()
	if !dayStart.checked.IsZero() && now.Sub(dayStart.checked) < dayStartRecheck {
		return dayStart.pressed
	}
	dayStart.checked = now
	info, err := os.Stat(dayStart.path)
	if err != nil {
		dayStart.modTime, dayStart.size, dayStart.pressed = time.Time{}, -1, 0
		return 0
	}
	if info.ModTime().Equal(dayStart.modTime) && info.Size() == dayStart.size {
		return dayStart.pressed
	}
	dayStart.modTime, dayStart.size, dayStart.pressed = info.ModTime(), info.Size(), 0
	var file struct {
		PressedRealMillis int64 `json:"pressedRealMillis"`
	}
	if data, err := os.ReadFile(dayStart.path); err == nil && json.Unmarshal(data, &file) == nil {
		dayStart.pressed = file.PressedRealMillis
	}
	return dayStart.pressed
}

// pressedGameMillis is the press on the game clock, 0 for none.
func pressedGameMillis() int64 {
	real := pressedReal()
	if real <= 0 {
		return 0
	}
	return real + calendarShift(real)
}

// StartOfDay is the start of the game day containing millis: 00:00 GMT-8, or
// a press of Start a new day that day before millis.
func StartOfDay(millis int64) int64 {
	start := BaseStartOfDay(millis)
	if p := pressedGameMillis(); p > start && p <= millis {
		return p
	}
	return start
}

// NewDayPausesBonus reports whether Start a new day was pressed on the game
// day of now; the challenge bonus is paused for the rest of that day.
func NewDayPausesBonus(now int64) bool {
	p := pressedGameMillis()
	return p > 0 && p >= BaseStartOfDay(now) && p <= now
}
