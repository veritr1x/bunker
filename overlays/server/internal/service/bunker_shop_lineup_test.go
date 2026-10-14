package service

import (
	"context"
	"testing"

	pb "lunar-tear/server/gen/proto"
)

func TestItemShopRefreshCostsGems(t *testing.T) {
	holder, users := harness(t)
	srv := NewShopServiceServer(users, users, holder)
	ctx := context.Background()
	users.user.Gem.FreeGem, users.user.Gem.PaidGem = 35, 0

	// Opening the shop starts the day's count at 1 (refresh 1 costs 10 gems).
	if _, err := srv.RefreshUserData(ctx, &pb.RefreshRequest{}); err != nil {
		t.Fatal(err)
	}
	if users.user.ShopReplaceable.LineupUpdateCount != 1 {
		t.Fatalf("count %d", users.user.ShopReplaceable.LineupUpdateCount)
	}
	if _, err := srv.RefreshUserData(ctx, &pb.RefreshRequest{IsGemUsed: true}); err != nil {
		t.Fatal(err)
	}
	if users.user.Gem.FreeGem != 25 || users.user.ShopReplaceable.LineupUpdateCount != 2 {
		t.Fatalf("after refresh 1: gems %d count %d", users.user.Gem.FreeGem, users.user.ShopReplaceable.LineupUpdateCount)
	}
	// Refresh 2 costs 30: only 25 left, so it is refused and nothing changes.
	if _, err := srv.RefreshUserData(ctx, &pb.RefreshRequest{IsGemUsed: true}); err == nil {
		t.Fatal("refresh allowed without enough gems")
	}
	if users.user.Gem.FreeGem != 25 || users.user.ShopReplaceable.LineupUpdateCount != 2 {
		t.Fatalf("refused refresh changed state: gems %d count %d", users.user.Gem.FreeGem, users.user.ShopReplaceable.LineupUpdateCount)
	}
	// Next day the count is back to 1.
	users.user.ShopReplaceable.LatestLineupUpdateDatetime -= 2 * 86400000
	srv.RefreshUserData(ctx, &pb.RefreshRequest{})
	if users.user.ShopReplaceable.LineupUpdateCount != 1 {
		t.Fatalf("count after the reset: %d", users.user.ShopReplaceable.LineupUpdateCount)
	}
}
