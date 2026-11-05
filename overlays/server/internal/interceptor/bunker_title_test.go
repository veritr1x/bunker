package interceptor

import (
	"context"
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
