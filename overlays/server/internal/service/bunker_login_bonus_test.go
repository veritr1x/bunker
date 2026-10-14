package service

import (
	"context"
	"strings"
	"testing"

	"lunar-tear/server/internal/userdata"

	emptypb "google.golang.org/protobuf/types/known/emptypb"
)

func TestEventLoginBonusesStampDaily(t *testing.T) {
	holder, users := harness(t)
	srv := NewLoginBonusServiceServer(users, users, holder)
	ctx := context.Background()
	const day = int64(86400000)
	launchEvent := int64(1627509600000) // login bonus 2 opens (launch), ends 2021-09-08
	users.user.LoginBonus.LatestRewardReceiveDatetime = 0

	setClock(t, launchEvent+day)
	gifts := len(users.user.Gifts.NotReceived)
	if _, err := srv.ReceiveStamp(ctx, &emptypb.Empty{}); err != nil {
		t.Fatal(err)
	}
	card, ok := users.user.Ext.EventLoginBonuses[2]
	if !ok || card.CurrentStampNumber != 1 {
		t.Fatalf("event card 2: %+v %v (cards %v)", card, ok, users.user.Ext.EventLoginBonuses)
	}
	if len(users.user.Gifts.NotReceived) < gifts+2 {
		t.Fatalf("gifts %d -> %d, want the everyday stamp and the event stamp", gifts, len(users.user.Gifts.NotReceived))
	}
	// Same day: nothing more.
	before := len(users.user.Gifts.NotReceived)
	srv.ReceiveStamp(ctx, &emptypb.Empty{})
	if len(users.user.Gifts.NotReceived) != before || users.user.Ext.EventLoginBonuses[2].CurrentStampNumber != 1 {
		t.Fatal("stamped twice in one day")
	}
	// Next day: the second stamp.
	setClock(t, launchEvent+2*day)
	srv.ReceiveStamp(ctx, &emptypb.Empty{})
	if users.user.Ext.EventLoginBonuses[2].CurrentStampNumber != 2 {
		t.Fatalf("day 2 stamp: %+v", users.user.Ext.EventLoginBonuses[2])
	}
	// The game is sent both cards.
	if rows := userdata.ProjectTables(users.user, []string{"IUserLoginBonus"})["IUserLoginBonus"]; !strings.Contains(rows, `"loginBonusId":2`) || !strings.Contains(rows, `"loginBonusId":1`) {
		t.Fatalf("IUserLoginBonus: %s", rows)
	}
}

func TestEventLoginBonusesNeedTheCalendar(t *testing.T) {
	_, users := harness(t)
	if open := openEventLoginBonuses(&users.user, 1627509600000+86400000); len(open) != 0 {
		t.Fatalf("%d dated cards open without the Original calendar", len(open))
	}
}
