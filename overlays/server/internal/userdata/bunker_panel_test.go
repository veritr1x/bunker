package userdata

import (
	"strings"
	"testing"

	"lunar-tear/server/internal/store"
)

// The Library shows an Anecdote's story page once its sheet is completed.
func TestLibraryShowsCompletedPagesOnly(t *testing.T) {
	defer func() { PanelPagesDone = nil }()
	PanelPagesDone = func(u *store.UserState) map[int32]int64 { return map[int32]int64{7: 1234} }
	got := projectTable("IUserWebviewPanelMission", store.UserState{UserId: 1})
	if !strings.Contains(got, `"webviewPanelMissionPageId":7`) || !strings.Contains(got, `"rewardReceiveDatetime":1234`) || strings.Count(got, "webviewPanelMissionPageId") != 1 {
		t.Fatalf("pages: %s", got)
	}
}
