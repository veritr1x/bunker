package service

import (
	"strings"
	"testing"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/userdata"
)

func TestBeginnerAndComebackCampaigns(t *testing.T) {
	_, users := harness(t)
	u := &users.user
	const day = int64(86400000)
	now := int64(1_800_000_000_000)

	// A player who started recently becomes a beginner once quest 1 is cleared, for 7 days.
	u.RegisterDatetime = now - day
	campaign.JoinBeginner(u, now)
	if u.Ext.Beginner.CampaignId != 0 {
		t.Fatal("beginner before clearing the unlock quest")
	}
	u.Quests[1] = store.UserQuestState{QuestId: 1, ClearCount: 1}
	campaign.JoinBeginner(u, now)
	if campaign.UserStatus(u, now+6*day) != campaign.TargetUserStatusBeginner || campaign.UserStatus(u, now+8*day) != campaign.TargetUserStatusAll {
		t.Fatalf("beginner status: %+v", u.Ext.Beginner)
	}
	if rows := userdata.ProjectTables(*u, []string{"IUserBeginnerCampaign"})["IUserBeginnerCampaign"]; !strings.Contains(rows, `"beginnerCampaignId":1`) {
		t.Fatalf("IUserBeginnerCampaign: %s", rows)
	}

	// Back after 40 days away: a comeback player for the campaign's term.
	later := now + 60*day
	campaign.JoinComeback(u, later-40*day, later)
	if u.Ext.Comeback.CampaignId == 0 || campaign.UserStatus(u, later+day) != campaign.TargetUserStatusComeback {
		t.Fatalf("comeback: %+v", u.Ext.Comeback)
	}
	// A short break is not a comeback.
	v := newMemUsers().user
	v.Quests[1] = store.UserQuestState{QuestId: 1, ClearCount: 1}
	campaign.JoinComeback(&v, later-3*day, later)
	if v.Ext.Comeback.CampaignId != 0 {
		t.Fatal("comeback after 3 days")
	}
}
