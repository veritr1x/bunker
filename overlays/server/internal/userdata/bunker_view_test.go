package userdata

import (
	"testing"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

const viewWeek = int64(7 * 24 * 3600 * 1000)

func setView(t *testing.T) {
	t.Helper()
	gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: gametime.Launch + 100*viewWeek, OriginalDates: true})
	t.Cleanup(func() { gametime.SetCalendar(nil) })
}

// Player data shows its times in the original-dates view; "forever" dates,
// latestVersion and other numbers stay.
func TestViewJSONMovesDatetimes(t *testing.T) {
	setView(t)
	in := `[{"acquisitionDatetime":1793499568858,"latestVersion":1793499568858,"endDatetime":253402300799000,"x":1793499568858,"startDatetime":0}]`
	want := `[{"acquisitionDatetime":1733019568858,"latestVersion":1793499568858,"endDatetime":253402300799000,"x":1793499568858,"startDatetime":0}]`
	if got := viewJSON(in); got != want {
		t.Fatalf("\n got %s\nwant %s", got, want)
	}
}

func TestViewJSONOffsetZeroIsIdentical(t *testing.T) {
	gametime.SetCalendar(nil)
	in := `[{"acquisitionDatetime":1793499568858}]`
	if got := viewJSON(in); got != in {
		t.Fatalf("changed with the view off: %s", got)
	}
}

// Both sides of a diff are in the view, so an unchanged player has no updates.
func TestDiffAfterSwitchSeesNoChange(t *testing.T) {
	setView(t)
	u := store.SeedUserState(1, "u", 1793499568858, model.DefaultPlatform)
	u.Weapons["w1"] = store.WeaponState{UserWeaponUuid: "w1", WeaponId: 101001, Level: 1, AcquisitionDatetime: 1793499568858}
	// Tables with key fields send only changed rows (others always send all).
	d := ComputeDelta(u, u, []string{"IUserWeapon"})
	for table, dd := range d {
		if dd.UpdateRecordsJson != "[]" {
			t.Fatalf("%s reported changes: %s", table, dd.UpdateRecordsJson)
		}
	}
}
