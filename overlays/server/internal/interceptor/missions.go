package interceptor

import (
	"context"
	"log"
	"strings"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/missions"
	"lunar-tear/server/internal/service"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/userdata"

	"google.golang.org/grpc"
)

// NewMissionInterceptor updates the player's missions after each request, from
// what the request changed in the save. It goes inside the diff interceptor so
// the client receives the mission changes with the request's own.
func NewMissionInterceptor(users store.UserRepository, sessions store.SessionRepository) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
		if skipDiffForMethod(info.FullMethod) || strings.HasPrefix(info.FullMethod, "/apb.api.data.") {
			return handler(ctx, req)
		}
		cat := missions.Current()
		userId := service.CurrentUserId(ctx, users, sessions)
		if cat == nil || userId == 0 {
			return handler(ctx, req)
		}
		before, err := users.LoadUser(userId)
		if err != nil {
			return handler(ctx, req)
		}
		resp, handlerErr := handler(ctx, req)
		if handlerErr != nil || resp == nil {
			return resp, handlerErr
		}
		var tracked store.UserState
		after, err := users.UpdateUser(userId, func(u *store.UserState) {
			tracked = store.CloneUserState(*u)
			cat.Track(&before, u, info.FullMethod, req, gametime.NowMillis())
		})
		if err != nil {
			log.Printf("[missions] %s: %v", info.FullMethod, err)
			return resp, nil
		}
		// A handler that fills in its own diff skips the diff interceptor's own
		// comparison (which then only sets the trailer), so add the mission changes here.
		if getter, ok := resp.(diffUserDataGetter); ok && hasDiffField(resp) {
			if existing := getter.GetDiffUserData(); len(existing) > 0 {
				changed := userdata.ChangedTables(&tracked, &after)
				for table, d := range userdata.ComputeDelta(&tracked, &after, changed) {
					existing[table] = d
				}
			}
		}
		return resp, nil
	}
}
