package gametime

import (
	"testing"
	"time"
)

func ms(t *testing.T, s string) int64 {
	t.Helper()
	v, err := time.Parse(time.RFC3339, s)
	if err != nil {
		t.Fatal(err)
	}
	return v.UnixMilli()
}

func TestStartOfDayIsGMT8AllYear(t *testing.T) {
	for _, c := range []struct{ at, want string }{
		{"2024-01-15T07:59:59Z", "2024-01-14T08:00:00Z"},
		{"2024-01-15T08:00:00Z", "2024-01-15T08:00:00Z"},
		{"2024-01-15T23:00:00Z", "2024-01-15T08:00:00Z"},
		// Summer, and the US DST switch days: still 08:00 UTC.
		{"2024-07-01T07:00:00Z", "2024-06-30T08:00:00Z"},
		{"2024-07-01T08:30:00Z", "2024-07-01T08:00:00Z"},
		{"2024-03-10T12:00:00Z", "2024-03-10T08:00:00Z"},
		{"2024-11-03T12:00:00Z", "2024-11-03T08:00:00Z"},
	} {
		if got := StartOfDay(ms(t, c.at)); got != ms(t, c.want) {
			t.Errorf("StartOfDay(%s) = %s, want %s", c.at, time.UnixMilli(got).UTC().Format(time.RFC3339), c.want)
		}
	}
}

func TestWeeklyVersionIsMondayGMT8(t *testing.T) {
	for _, c := range []struct{ at, want string }{
		{"2024-07-01T07:59:59Z", "2024-06-24T08:00:00Z"}, // Sunday 23:59 GMT-8
		{"2024-07-01T08:00:00Z", "2024-07-01T08:00:00Z"}, // Monday 00:00 GMT-8
		{"2024-07-07T23:00:00Z", "2024-07-01T08:00:00Z"},
		{"2024-07-08T07:00:00Z", "2024-07-01T08:00:00Z"},
		{"2024-01-08T08:00:00Z", "2024-01-08T08:00:00Z"},
	} {
		if got := WeeklyVersion(ms(t, c.at)); got != ms(t, c.want) {
			t.Errorf("WeeklyVersion(%s) = %s, want %s", c.at, time.UnixMilli(got).UTC().Format(time.RFC3339), c.want)
		}
	}
}

func TestBigHuntScheduleStartsAWeek(t *testing.T) {
	// m_big_hunt_weekly_attribute_score_reward_group_schedule starts (Monday 08:00 UTC).
	for _, v := range []int64{1645430400000, 1676880000000} {
		if WeeklyVersion(v) != v || StartOfDay(v) != v {
			t.Errorf("%d is not a game week start", v)
		}
	}
}

func TestUpgradeWeekVersion(t *testing.T) {
	legacy := ms(t, "2024-07-01T00:00:00Z") // old Monday 00:00 UTC key
	if !IsLegacyWeekVersion(legacy) {
		t.Fatal("old key not recognised")
	}
	want := WeeklyVersion(ms(t, "2024-07-03T12:00:00Z"))
	if got := UpgradeWeekVersion(legacy); got != want {
		t.Fatalf("upgrade = %d, want the GMT-8 week of the same Monday %d", got, want)
	}
	// New keys, zero and odd values stay.
	for _, v := range []int64{want, 0, ms(t, "2024-07-02T00:00:00Z")} {
		if UpgradeWeekVersion(v) != v {
			t.Errorf("UpgradeWeekVersion(%d) changed it", v)
		}
	}
	// The week in progress at the switch is not closed early: Sunday evening
	// UTC is still in it.
	if UpgradeWeekVersion(legacy) < WeeklyVersion(ms(t, "2024-07-07T22:00:00Z")) {
		t.Fatal("week closed early")
	}
}

func TestUpgradeDayVersion(t *testing.T) {
	legacy := ms(t, "2024-07-02T00:00:00Z")
	// Seen before 08:00 UTC that day: everything happened on the GMT-8 day before.
	if got := UpgradeDayVersion(legacy, ms(t, "2024-07-02T05:00:00Z")); got != ms(t, "2024-07-01T08:00:00Z") {
		t.Errorf("early: %s", time.UnixMilli(got).UTC())
	}
	// Seen later: it may have been today, so it counts as today (no second reward).
	if got := UpgradeDayVersion(legacy, ms(t, "2024-07-02T15:00:00Z")); got != ms(t, "2024-07-02T08:00:00Z") {
		t.Errorf("late: %s", time.UnixMilli(got).UTC())
	}
	// An old day long past maps to a past day either way.
	if got := UpgradeDayVersion(legacy, ms(t, "2024-07-09T15:00:00Z")); got != ms(t, "2024-07-02T08:00:00Z") {
		t.Errorf("past: %s", time.UnixMilli(got).UTC())
	}
	newKey := ms(t, "2024-07-02T08:00:00Z")
	if UpgradeDayVersion(newKey, newKey+1) != newKey || UpgradeDayVersion(0, newKey) != 0 {
		t.Error("new keys and zero must stay")
	}
}
