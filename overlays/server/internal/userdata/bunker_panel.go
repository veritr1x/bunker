package userdata

import (
	"sort"

	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// PanelPagesDone gives the Anecdote story pages a player completed (page id ->
// time), from the panel sheets (missions/panels.go); set by the service. Nil:
// every page counts as done, as before panel sheets.
var PanelPagesDone func(u *store.UserState) map[int32]int64

func panelPagesDone(user store.UserState) string {
	done := PanelPagesDone(&user)
	ids := make([]int, 0, len(done))
	for id := range done {
		ids = append(ids, int(id))
	}
	sort.Ints(ids)
	records := make([]map[string]any, 0, len(ids))
	for _, id := range ids {
		records = append(records, map[string]any{
			"userId":                    user.UserId,
			"webviewPanelMissionPageId": int32(id),
			"rewardReceiveDatetime":     done[int32(id)],
			"latestVersion":             done[int32(id)],
		})
	}
	s, _ := utils.EncodeJSONMaps(records...)
	return s
}
