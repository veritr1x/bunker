package service

import (
	"testing"
	"time"

	"lunar-tear/server/internal/campaign"
)

func TestGreatSuccess(t *testing.T) {
	if exp, great := rollGreatSuccess(1000, 100, func(int) int { return 99 }); !great || exp != 1500 {
		t.Fatalf("roll 99 at 100‰: %d %v", exp, great)
	}
	if exp, great := rollGreatSuccess(1000, 100, func(int) int { return 100 }); great || exp != 1000 {
		t.Fatalf("roll 100 at 100‰: %d %v", exp, great)
	}
	if _, great := rollGreatSuccess(0, 1000, func(int) int { return 0 }); great {
		t.Fatal("great success with no experience")
	}
}

// Glorious Success Rate Up campaigns raise the chance, not the experience.
// 19 Aug – 14 Sep 2021 had one for all characters and all weapons, effect
// ADDITIONAL_PER_MILE 800: +80‰ on top of the usual 100‰.
func TestGreatSuccessCampaign(t *testing.T) {
	cat := loadMaster(t).Get()
	f := campaign.Filter{NowMillis: time.Date(2021, 9, 1, 0, 0, 0, 0, time.UTC).UnixMilli(), UserStatus: campaign.TargetUserStatusAll}
	if got := cat.Campaign.CostumeGreatSuccessBonus(campaign.CostumeTarget{CostumeId: 10100}, f).Apply(greatSuccessBasePermil); got != 180 {
		t.Fatalf("character rate during campaign = %d‰, want 180", got)
	}
	if got := cat.Campaign.WeaponGreatSuccessBonus(campaign.WeaponTarget{WeaponId: 101001}, f).Apply(greatSuccessBasePermil); got != 180 {
		t.Fatalf("weapon rate during campaign = %d‰, want 180", got)
	}
}
