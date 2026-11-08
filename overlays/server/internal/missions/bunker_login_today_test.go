package missions

import (
	"testing"
	"time"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/store"
)

// setGameClock moves the game clock to at until the test ends.
func setGameClock(t *testing.T, at int64) {
	t.Helper()
	gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: gametime.Launch, Speed: 1, JumpMillis: at - time.Now().UnixMilli()})
	t.Cleanup(func() { gametime.SetCalendar(nil) })
}

// A daily "Log in" mission clears on any request of the day, also when the
// day's login was already counted before the mission was tracked (a new
// player is saved as logged in at creation, and a mission can open later in
// the day).
func TestDailyLoginMissionsClearAfterTheDaysLogin(t *testing.T) {
	cat, st, uid, _ := realSave(t)
	now := afterLastLogin(t, st, uid)
	u, err := st.UpdateUser(uid, func(u *store.UserState) {
		u.Login.LastLoginDatetime = now // logged in already today
		for _, m := range cat.ByKind["login"] {
			delete(u.Missions, m.MissionId)
		}
		before := store.CloneUserState(*u)
		cat.Track(&before, u, "/apb.api.user.UserService/GameStart", nil, now+1000)
	})
	if err != nil {
		t.Fatal(err)
	}
	var daily int
	for _, m := range cat.ByKind["login"] {
		if !m.Daily() || !cat.active(m, &u, now+1000) {
			continue
		}
		daily++
		if rec := u.Missions[m.MissionId]; rec.MissionProgressStatusType != StatusClear {
			t.Errorf("daily login mission %d: %+v", m.MissionId, rec)
		}
	}
	if daily == 0 {
		t.Fatal("no daily login missions active")
	}
}
