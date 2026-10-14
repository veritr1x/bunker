package campaign

import (
	"log"
	"sync"
	"time"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// Beginner and comeback players. Some quest and enhance campaigns are only
// for new players (TargetUserStatusBeginner) or for players returning after a
// break (TargetUserStatusComeback):
//   - beginner (m_beginner_campaign): a player who started during the judge
//     window gets GrantCampaignTermDayCount days from clearing the unlock quest;
//   - comeback (m_comeback_campaign): a first login of the day after at least
//     ComebackJudgeDayCount days away, during the judge window, gives
//     GrantCampaignTermDayCount days from that login.
// The game shows both through IUserBeginnerCampaign and IUserComebackCampaign.

const dayMillis = int64(24 * time.Hour / time.Millisecond)

var beginnerCampaigns = sync.OnceValue(func() []masterdata.EntityMBeginnerCampaign {
	rows, err := utils.ReadTable[masterdata.EntityMBeginnerCampaign]("m_beginner_campaign")
	if err != nil {
		log.Printf("[campaign] m_beginner_campaign: %v", err)
	}
	return rows
})

var comebackCampaigns = sync.OnceValue(func() []masterdata.EntityMComebackCampaign {
	rows, err := utils.ReadTable[masterdata.EntityMComebackCampaign]("m_comeback_campaign")
	if err != nil {
		log.Printf("[campaign] m_comeback_campaign: %v", err)
	}
	return rows
})

// UserStatus is the campaign group the player is in at now.
func UserStatus(u *store.UserState, now int64) TargetUserStatusType {
	if c := u.Ext.Beginner; c.CampaignId != 0 {
		for _, b := range beginnerCampaigns() {
			if b.BeginnerCampaignId == c.CampaignId && now < c.Datetime+int64(b.GrantCampaignTermDayCount)*dayMillis {
				return TargetUserStatusBeginner
			}
		}
	}
	if c := u.Ext.Comeback; c.CampaignId != 0 {
		for _, b := range comebackCampaigns() {
			if b.ComebackCampaignId == c.CampaignId && now < c.Datetime+int64(b.GrantCampaignTermDayCount)*dayMillis {
				return TargetUserStatusComeback
			}
		}
	}
	return TargetUserStatusAll
}

// FilterFor is the campaign filter for the player at now.
func FilterFor(u *store.UserState, now int64) Filter {
	if u == nil {
		return Filter{NowMillis: now, UserStatus: TargetUserStatusAll}
	}
	return Filter{NowMillis: now, UserStatus: UserStatus(u, now)}
}

// JoinBeginner registers a new player for the beginner campaign once they
// have cleared its unlock quest.
func JoinBeginner(u *store.UserState, now int64) {
	if u.Ext.Beginner.CampaignId != 0 {
		return
	}
	for _, b := range beginnerCampaigns() {
		if u.RegisterDatetime < b.BeginnerJudgeStartDatetime || u.RegisterDatetime > b.BeginnerJudgeEndDatetime {
			continue
		}
		if u.Quests[b.CampaignUnlockQuestId].ClearCount == 0 {
			continue
		}
		u.Ext.Beginner = store.CampaignJoinState{CampaignId: b.BeginnerCampaignId, Datetime: now}
		log.Printf("[campaign] user %d: beginner campaign %d for %d days", u.UserId, b.BeginnerCampaignId, b.GrantCampaignTermDayCount)
		return
	}
}

// JoinComeback starts a comeback campaign on the first login of a day when
// the previous login was long enough ago.
func JoinComeback(u *store.UserState, previousLogin, now int64) {
	if previousLogin == 0 {
		return
	}
	for _, b := range comebackCampaigns() {
		if now < b.ComebackJudgeStartDatetime || now > b.ComebackJudgeEndDatetime {
			continue
		}
		if now-previousLogin < int64(b.ComebackJudgeDayCount)*dayMillis || u.Quests[b.CampaignUnlockQuestId].ClearCount == 0 {
			continue
		}
		u.Ext.Comeback = store.CampaignJoinState{CampaignId: b.ComebackCampaignId, Datetime: now}
		u.Login.LastComebackLoginDatetime = now
		log.Printf("[campaign] user %d: comeback campaign %d after %d days away", u.UserId, b.ComebackCampaignId, (now-previousLogin)/dayMillis)
		return
	}
}
