package service

import (
	"time"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"

	"google.golang.org/protobuf/types/known/timestamppb"
)

// freeSummonBadges are the times the menu's Summon button shows its "free"
// badge (MenuGachaBadgeInfo, GachaFreeBadgeTermCollection in the client): for
// each open summon with a free daily draw, from today while it is unused,
// otherwise from the next daily reset, until the summon ends. Sent at game
// start and with every draw, so the badge goes once the draw is used.
func freeSummonBadges(catalog []store.GachaCatalogEntry, user *store.UserState, now int64) []*pb.MenuGachaBadgeInfo {
	today := gametime.StartOfDay(now)
	tomorrow := today + int64(24*time.Hour/time.Millisecond)
	var out []*pb.MenuGachaBadgeInfo
	for _, entry := range catalog {
		if !gachaActiveAt(entry, now) || entry.GachaModeType == model.GachaModeStepup || entry.GachaAutoResetType != model.GachaAutoResetDaily {
			continue
		}
		for _, p := range entry.PricePhases {
			if p.Price != 0 || p.LimitExecCount <= 0 {
				continue
			}
			from := today
			if user == nil {
				continue
			}
			if st := user.Ext.GachaExec[p.PhaseId]; st.Day == today && st.Count >= p.LimitExecCount {
				from = tomorrow
			}
			until := entry.EndDatetime
			if until == 0 {
				until = from + int64(365*24*time.Hour/time.Millisecond)
			}
			if from < until {
				out = append(out, &pb.MenuGachaBadgeInfo{
					DisplayStartDatetime: timestamppb.New(time.UnixMilli(from)),
					DisplayEndDatetime:   timestamppb.New(time.UnixMilli(until)),
				})
			}
		}
	}
	return out
}
