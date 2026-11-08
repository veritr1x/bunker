package service

import (
	"context"
	"strings"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/userdata"
)

// GetUserData must send every table the client is told to ask for, Bunker's
// own included (they were sent empty at sign-in when missing from a second,
// hand-kept list).
func TestGetUserDataSendsEveryNamedTable(t *testing.T) {
	_, users := harness(t)
	users.user.Ext.Beginner.CampaignId = 1
	users.user.Ext.Beginner.Datetime = users.user.RegisterDatetime
	names := defaultTableNames()
	res, err := NewDataServiceServer(users, users).GetUserData(context.Background(), &pb.UserDataGetRequest{TableName: names})
	if err != nil {
		t.Fatal(err)
	}
	want := userdata.ProjectTables(users.user, names)
	for _, name := range names {
		// Some rows carry the time of the call, so compare only emptiness.
		if (res.UserDataJson[name] == "[]") != (want[name] == "[]") {
			t.Errorf("%s: sent %.120s, has %.120s", name, res.UserDataJson[name], want[name])
		}
	}
	for _, name := range []string{"IUserLimitedOpen", "IUserBeginnerCampaign"} {
		if !strings.Contains(res.UserDataJson[name], `"userId"`) {
			t.Errorf("%s sent empty: %s", name, res.UserDataJson[name])
		}
	}
}
