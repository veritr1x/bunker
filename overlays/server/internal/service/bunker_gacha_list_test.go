package service

import (
	"context"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/model"
)

// The reruns Bunker added (506's in 2023 and 2024, 124's second chance) run
// on the calendar with their own dates; with it off they are all open, and
// the list showed their banner two or three times. It shows each once.
func TestSummonListShowsEachBannerOnce(t *testing.T) {
	holder, users := harness(t)
	cat := holder.Get()
	banner := map[int32]string{}
	runs := map[string]int{}
	for _, e := range cat.GachaEntries {
		banner[e.GachaId] = e.BannerAssetName
		if e.BannerAssetName == "limited_506" {
			runs[e.BannerAssetName]++
		}
	}
	if runs["limited_506"] < 2 {
		t.Skip("needs the summon rules' reruns of 506")
	}
	srv := NewGachaServiceServer(users, users, holder)
	resp, err := srv.GetGachaList(context.Background(), &pb.GetGachaListRequest{GachaLabelType: []int32{model.GachaLabelPremium}})
	if err != nil {
		t.Fatal(err)
	}
	listed := map[string][]int32{}
	for _, g := range resp.Gacha {
		if name := banner[g.GachaId]; name != "" {
			listed[name] = append(listed[name], g.GachaId)
		}
	}
	if len(listed["limited_506"]) != 1 {
		t.Errorf("limited_506 listed as %v", listed["limited_506"])
	}
	for name, ids := range listed {
		if len(ids) > 1 {
			t.Errorf("%s listed %d times: %v", name, len(ids), ids)
		}
	}
}

// Summons without a banner name are never merged.
func TestFirstOfBannerKeepsUnnamedSummons(t *testing.T) {
	seen := bannerSeen{}
	if !seen.first("limited_506") || seen.first("limited_506") || !seen.first("") || !seen.first("") {
		t.Fatal("first of a banner")
	}
}
