package interceptor

// Back to the title screen, the game's own way, so a change made in Pod
// Programs beside the running game reaches it without restarting the app:
// signing in again from the title screen reloads the player's save and checks
// the master data version (the game keeps one copy per version).
//
// When a call fails, the 3.7.1 client's ErrorHandlingInterceptor
// (Adam.Framework.Network.Interceptors) reads the response trailers into a
// CommonResponse (ResponseContextExtensions.GetCommonResponse) and branches on
// x-apb-screen-transition-type (ScreenTransitionType: 1 Stay, 2 FunctionTop,
// 3 Title). For Title it calls HandleNet.ShowMoveTitleError(messageTextId,
// messageCode, detail, messageText, maintenanceDateTime):
//
//   - messageCode picks a special dialog for HandleNet's codes (100000/100001
//     maintenance, 100002 maintenance page, 102002 ban, 103000 force update);
//     any other code shows the plain error dialog, titled "Refresh" for
//     104000 (HandleNet.DateUpdateId). InterceptorSettings.IgnoreErrorCodes
//     (290041, 290043, 290044) are not shown at all.
//   - messageTextId names the dialog text: NetworkTextKey.ConvertTextKey makes
//     it "nt.Network.<id>", and a key the game lacks falls back to the title
//     error text (HandleNet.GetErrorTextKey). Without it the game hangs with
//     its menus hidden. 900000 is the game's own "Returning to title screen."
//   - messageText is used only as a maintenance message.
//
// Checked on the Android emulator: "Refresh / Process failed. Returning to
// title screen.", OK, the title screen in the same process, and Tap to Start
// signs in again with GetLatestMasterDataVersion and a full GetUserData.

import (
	"context"
	"log"
	"strings"
	"sync/atomic"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// The game's own "back to the title screen" error.
var titleTrailer = metadata.Pairs(
	"x-apb-screen-transition-type", "3",
	"x-apb-message-code", "104000",
	"x-apb-message-text-id", "900000",
)

var titlePending atomic.Bool

// RequestTitle sends the game back to its title screen on its next call.
func RequestTitle() {
	titlePending.Store(true)
	log.Printf("[Title] the game returns to its title screen on its next call")
}

// TitlePending reports whether the game has yet to be sent back.
func TitlePending() bool { return titlePending.Load() }

// titleKeeps reports calls that go through while a return is pending: a
// battle or exploration result the player has just played (failing it would
// lose the run), and the calls the game makes while signing in, which load
// everything again anyway (they also end the wait).
func titleKeeps(method string) (keep, signsIn bool) {
	switch method[strings.LastIndex(method, "/")+1:] {
	case "Auth", "RegisterUser", "GetAndroidArgs", "GetLatestMasterDataVersion", "GetReviewServerConfig":
		return true, true
	case "FinishWave", "FinishMainQuest", "FinishEventQuest", "FinishExtraQuest",
		"FinishBigHuntQuest", "SaveBigHuntBattleInfo", "FinishExplore":
		return true, false
	}
	return false, false
}

// ReturnToTitle fails the first call after RequestTitle with the title
// transition; titleKeeps lists the calls that go through.
func ReturnToTitle(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
	if !titlePending.Load() {
		return handler(ctx, req)
	}
	if keep, signsIn := titleKeeps(info.FullMethod); keep {
		if signsIn && titlePending.Swap(false) {
			log.Printf("[Title] %s: the game is signing in again", info.FullMethod)
		}
		return handler(ctx, req)
	}
	if !titlePending.Swap(false) {
		return handler(ctx, req)
	}
	if err := grpc.SetTrailer(ctx, titleTrailer); err != nil {
		log.Printf("[Title] set trailer on %s: %v", info.FullMethod, err)
	}
	log.Printf("[Title] %s -> back to the title screen", info.FullMethod)
	return nil, status.Error(codes.FailedPrecondition, "returning to the title screen")
}
