package interceptor

import (
	"context"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/store"

	"google.golang.org/grpc"
)

// countingUsers counts full save loads; other calls are not expected.
type countingUsers struct {
	store.UserRepository
	loads int
}

func (c *countingUsers) DefaultUserId() (int64, error) { return 1, nil }
func (c *countingUsers) LoadUser(int64) (store.UserState, error) {
	c.loads++
	return store.UserState{UserId: 1}, nil
}

// UpdateSequence goes through the diff and mission interceptors without a
// load of the save, and keeps the handler's own diff.
func TestUpdateSequenceSkipsSaveLoads(t *testing.T) {
	users := &countingUsers{}
	info := &grpc.UnaryServerInfo{FullMethod: "/apb.api.gimmick.GimmickService/UpdateSequence"}
	own := map[string]*pb.DiffData{"IUserGimmickSequence": {UpdateRecordsJson: "[{}]", DeleteKeysJson: "[]"}}
	handler := func(context.Context, any) (any, error) {
		return &pb.UpdateSequenceResponse{DiffUserData: own}, nil
	}
	missions := func(ctx context.Context, req any) (any, error) {
		return NewMissionInterceptor(users, nil)(ctx, req, info, handler)
	}
	resp, err := NewDiffInterceptor(users, nil)(context.Background(), &pb.UpdateSequenceRequest{}, info, missions)
	if err != nil {
		t.Fatal(err)
	}
	if users.loads != 0 {
		t.Fatalf("loaded the save %d times", users.loads)
	}
	if d := resp.(*pb.UpdateSequenceResponse).DiffUserData; len(d) != 1 || d["IUserGimmickSequence"] == nil {
		t.Fatalf("diff %v", d)
	}
}
