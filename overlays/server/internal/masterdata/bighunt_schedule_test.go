package masterdata

import "testing"

func TestBigHuntScheduleFollowsTheClock(t *testing.T) {
	c := &BigHuntCatalog{ActiveScheduleId: 1, schedules: []EntityMBigHuntSchedule{
		{BigHuntScheduleId: 1, ChallengeStartDatetime: 100, ChallengeEndDatetime: 199},
		{BigHuntScheduleId: 2, ChallengeStartDatetime: 300, ChallengeEndDatetime: 399},
	}}
	for _, step := range []struct {
		now  int64
		want int32
	}{{150, 1}, {350, 2}, {250, 2}, {500, 2}} {
		if got := c.ScheduleAt(step.now); got != step.want {
			t.Errorf("at %d: schedule %d, want %d", step.now, got, step.want)
		}
	}
	if (&BigHuntCatalog{ActiveScheduleId: 7}).ScheduleAt(0) != 7 {
		t.Error("catalog without schedules lost its start-up schedule")
	}
}
