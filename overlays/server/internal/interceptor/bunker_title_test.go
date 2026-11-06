package interceptor

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// trailers collects what a handler sets with grpc.SetTrailer.
type trailers struct{ md metadata.MD }

func (t *trailers) Method() string                  { return "" }
func (t *trailers) SetHeader(metadata.MD) error     { return nil }
func (t *trailers) SendHeader(metadata.MD) error    { return nil }
func (t *trailers) SetTrailer(md metadata.MD) error { t.md = metadata.Join(t.md, md); return nil }

func call(method string) (error, metadata.MD, bool) {
	stream := &trailers{}
	ctx := grpc.NewContextWithServerTransportStream(context.Background(), stream)
	ran := false
	_, err := ReturnToTitle(ctx, nil, &grpc.UnaryServerInfo{FullMethod: method}, func(context.Context, any) (any, error) {
		ran = true
		return nil, nil
	})
	return err, stream.md, ran
}

func TestReturnToTitleFailsOneCallWithTheGamesTitleError(t *testing.T) {
	titlePending.Store(false)
	if err, _, ran := call("/apb.api.gift.GiftService/GetGiftList"); err != nil || !ran {
		t.Fatalf("not armed: err=%v ran=%v", err, ran)
	}
	RequestTitle()
	err, md, ran := call("/apb.api.gift.GiftService/GetGiftList")
	if ran || status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("armed call: err=%v ran=%v", err, ran)
	}
	for key, want := range map[string]string{"x-apb-screen-transition-type": "3", "x-apb-message-code": "104000", "x-apb-message-text-id": "900000"} {
		if got := md.Get(key); len(got) != 1 || got[0] != want {
			t.Errorf("%s = %v, want %s", key, got, want)
		}
	}
	if err, _, ran := call("/apb.api.gift.GiftService/GetGiftList"); err != nil || !ran {
		t.Fatalf("second call: err=%v ran=%v", err, ran)
	}
}

func TestReturnToTitleLetsBattleResultsThroughAndWaits(t *testing.T) {
	RequestTitle()
	if err, _, ran := call("/apb.api.battle.BattleService/FinishWave"); err != nil || !ran {
		t.Fatalf("FinishWave: err=%v ran=%v", err, ran)
	}
	if !TitlePending() {
		t.Fatal("a battle result ended the wait")
	}
	if err, _, _ := call("/apb.api.quest.QuestService/StartMainQuest"); status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("next call: %v", err)
	}
}

func TestReturnToTitleEndsWhenTheGameSignsIn(t *testing.T) {
	RequestTitle()
	if err, _, ran := call("/apb.api.user.UserService/Auth"); err != nil || !ran {
		t.Fatalf("Auth: err=%v ran=%v", err, ran)
	}
	if TitlePending() {
		t.Fatal("signing in left the return pending")
	}
}

func TestTheLaunchersHealthCheckIsNotTheGamesCall(t *testing.T) {
	titlePending.Store(false)
	RequestTitle()
	// Two changes in a row: Lunar Tear starts again with the return pending and checks itself.
	if err, _, ran := call("/grpc.health.v1.Health/Check"); err != nil || !ran {
		t.Fatalf("health check: err=%v ran=%v", err, ran)
	}
	if !TitlePending() {
		t.Fatal("the health check used up the return to the title screen")
	}
	if err, _, ran := call("/apb.api.gift.GiftService/GetGiftList"); ran || status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("the game's next call: err=%v ran=%v", err, ran)
	}
	titlePending.Store(false)
}

func withMarker(t *testing.T) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "title.now")
	titlePending.Store(false)
	markerWritten.Store(false)
	SetTitleMarker(path)
	t.Cleanup(func() { SetTitleMarker(""); titlePending.Store(false); markerWritten.Store(false) })
	return path
}

func exists(path string) bool { _, err := os.Stat(path); return err == nil }

func TestARequestWritesTheMarkerAndTheRedirectRemovesIt(t *testing.T) {
	path := withMarker(t)
	RequestTitle()
	if !exists(path) {
		t.Fatal("no marker for the game")
	}
	if err, _, ran := call("/apb.api.gift.GiftService/GetGiftList"); ran || status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("the next call: err=%v ran=%v", err, ran)
	}
	if exists(path) || TitlePending() {
		t.Fatal("the marker or the request outlived the redirect")
	}
}

func TestAMarkerTheGameRemovedMeansItAlreadyWentBack(t *testing.T) {
	path := withMarker(t)
	RequestTitle()
	os.Remove(path) // title_now.c showed the dialog
	if err, _, ran := call("/apb.api.gift.GiftService/GetGiftList"); err != nil || !ran {
		t.Fatalf("the next call was failed again: err=%v ran=%v", err, ran)
	}
	if TitlePending() {
		t.Fatal("still pending")
	}
}

func TestSigningInRemovesTheMarker(t *testing.T) {
	path := withMarker(t)
	RequestTitle()
	if err, _, ran := call("/apb.api.user.UserService/Auth"); err != nil || !ran {
		t.Fatalf("auth: err=%v ran=%v", err, ran)
	}
	if exists(path) || TitlePending() {
		t.Fatal("the marker or the request outlived signing in")
	}
}

func TestAMarkerThatCouldNotBeWrittenStillRedirects(t *testing.T) {
	path := filepath.Join(t.TempDir(), "missing-folder", "title.now")
	titlePending.Store(false)
	SetTitleMarker(path)
	t.Cleanup(func() { SetTitleMarker(""); titlePending.Store(false); markerWritten.Store(false) })
	RequestTitle()
	if err, _, ran := call("/apb.api.gift.GiftService/GetGiftList"); ran || status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("without a marker the next call must still redirect: err=%v ran=%v", err, ran)
	}
}

func TestAStaleMarkerIsRemovedAtStart(t *testing.T) {
	path := filepath.Join(t.TempDir(), "title.now")
	os.WriteFile(path, nil, 0o644)
	titlePending.Store(false)
	SetTitleMarker(path)
	t.Cleanup(func() { SetTitleMarker("") })
	if exists(path) {
		t.Fatal("a marker from an earlier run was kept")
	}
}
