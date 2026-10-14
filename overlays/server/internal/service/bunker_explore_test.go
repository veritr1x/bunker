package service

import (
	"context"
	"testing"

	pb "lunar-tear/server/gen/proto"
)

func TestExploreRewardsFollowTheGrade(t *testing.T) {
	holder, users := harness(t)
	cat := holder.Get()
	srv := NewExploreServiceServer(users, users, holder)
	ticket := cat.GameConfig.ConsumableItemIdForExploreTicket
	ctx := context.Background()

	// Hard (explore 11) takes 10 tickets: refused with 9, played with 10.
	users.user.ConsumableItems[ticket] = 9
	if _, err := srv.StartExplore(ctx, &pb.StartExploreRequest{ExploreId: 11, UseConsumableItemId: ticket}); err == nil {
		t.Fatal("started hard with too few tickets")
	}
	if users.user.ConsumableItems[ticket] != 9 {
		t.Fatalf("tickets taken on a refused start: %d", users.user.ConsumableItems[ticket])
	}
	users.user.ConsumableItems[ticket] = 10
	if _, err := srv.StartExplore(ctx, &pb.StartExploreRequest{ExploreId: 11, UseConsumableItemId: ticket}); err != nil {
		t.Fatal(err)
	}
	if users.user.ConsumableItems[ticket] != 0 || !users.user.Explore.IsUseExploreTicket {
		t.Fatalf("tickets %d, ticket flag %v", users.user.ConsumableItems[ticket], users.user.Explore.IsUseExploreTicket)
	}

	low, err := srv.FinishExplore(ctx, &pb.FinishExploreRequest{ExploreId: 11, Score: 0})
	if err != nil {
		t.Fatal(err)
	}
	high, err := srv.FinishExplore(ctx, &pb.FinishExploreRequest{ExploreId: 11, Score: 1 << 30})
	if err != nil {
		t.Fatal(err)
	}
	if low.AcquireStaminaCount != 5 || high.AcquireStaminaCount != 30 || low.AssetGradeIconId == high.AssetGradeIconId {
		t.Fatalf("stamina %d/%d, grades %d/%d", low.AcquireStaminaCount, high.AcquireStaminaCount, low.AssetGradeIconId, high.AssetGradeIconId)
	}
	draws := int32(0)
	for _, r := range high.ExploreReward {
		if r.PossessionType == 5 {
			draws += r.Count
		}
		if r.Count <= 0 {
			t.Fatalf("empty reward %v", r)
		}
	}
	if len(high.ExploreReward) == 0 || draws > 11 {
		t.Fatalf("hard rewards: %v", high.ExploreReward)
	}
}
