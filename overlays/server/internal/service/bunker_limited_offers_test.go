package service

import (
	"context"
	"strings"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/userdata"
)

func TestLimitedOffersOpenForTheirSalePeriod(t *testing.T) {
	holder, users := harness(t)
	offers, shops := masterdata.LimitedOffers()
	if len(offers) < 30 || len(shops) == 0 {
		t.Fatalf("%d offers, %d shops", len(offers), len(shops))
	}
	rows := userdata.ProjectTables(users.user, []string{"IUserLimitedOpen"})["IUserLimitedOpen"]
	if !strings.Contains(rows, `"limitedOpenTargetType":5`) || !strings.Contains(rows, `"limitedOpenTargetType":1`) {
		t.Fatalf("IUserLimitedOpen: %.300s", rows)
	}

	var o masterdata.LimitedOffer
	for _, x := range offers {
		if x.CloseDatetime-x.OpenDatetime > 86400000 {
			o = x
			break
		}
	}
	srv := NewShopServiceServer(users, users, holder)
	ctx := context.Background()
	buy := func() error {
		_, err := srv.CreatePurchaseTransaction(ctx, &pb.CreatePurchaseTransactionRequest{ShopId: o.ShopId, ShopItemId: o.ShopItemId})
		return err
	}
	setClock(t, o.CloseDatetime+1000)
	if buy() == nil {
		t.Fatal("bought a closed offer")
	}
	setClock(t, o.OpenDatetime+1000)
	if err := buy(); err != nil {
		t.Fatalf("open offer: %v", err)
	}
	if buy() == nil {
		t.Fatal("bought an offer twice")
	}
}
