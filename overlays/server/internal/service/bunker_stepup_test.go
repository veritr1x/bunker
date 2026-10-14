package service

import (
	"context"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// shownStep checks the summon as the client lists it (one Gacha per step,
// each with its own price; the client shows the one whose StepNumber is
// CurrentStepNumber) and returns the step shown.
func shownStep(t *testing.T, srv *GachaServiceServer, entry store.GachaCatalogEntry) int32 {
	t.Helper()
	resp, err := srv.GetGachaList(context.Background(), &pb.GetGachaListRequest{GachaLabelType: []int32{entry.GachaLabelType}})
	if err != nil {
		t.Fatal(err)
	}
	var steps []*pb.Gacha
	for _, g := range resp.Gacha {
		if c := g.GetGachaModeStepupComposition(); c != nil && c.GachaStepGroupId == entry.GroupId {
			steps = append(steps, g)
		}
	}
	if len(steps) != int(entry.MaxStepNumber) {
		t.Fatalf("%d steps listed, summon has %d", len(steps), entry.MaxStepNumber)
	}
	current := steps[0].GetGachaModeStepupComposition().CurrentStepNumber
	var shown *pb.Gacha
	for i, g := range steps {
		c := g.GetGachaModeStepupComposition()
		if c.StepNumber != int32(i+1) || c.CurrentStepNumber != current {
			t.Fatalf("step %d listed as step %d of current %d", i+1, c.StepNumber, c.CurrentStepNumber)
		}
		if len(g.GachaPricePhase) != 1 || g.GachaPricePhase[0].GachaPricePhaseId != entry.PricePhases[i].PhaseId {
			t.Fatalf("step %d prices %v", i+1, g.GachaPricePhase)
		}
		if c.StepNumber == current {
			shown = g
		}
	}
	if shown == nil || !shown.GachaPricePhase[0].IsEnabled {
		t.Fatalf("no enabled Gacha for current step %d", current)
	}
	// The client asks for and draws the step by its own id.
	got, err := srv.GetGacha(context.Background(), &pb.GetGachaRequest{GachaId: []int32{shown.GachaId}})
	if err != nil || got.Gacha[shown.GachaId].GetGachaModeStepupComposition().GetStepNumber() != current {
		t.Fatalf("GetGacha %d: %v %v", shown.GachaId, got, err)
	}
	return current
}

func TestStepUpSummonMovesToNextStep(t *testing.T) {
	holder, users := harness(t)
	cat := holder.Get()
	var entry store.GachaCatalogEntry
	for _, e := range cat.GachaEntries {
		if e.GachaModeType == model.GachaModeStepup && e.MaxStepNumber > 1 {
			entry = e
			break
		}
	}
	if entry.GachaId == 0 {
		t.Fatal("no step-up summon")
	}
	setClock(t, entry.StartDatetime+1)
	srv := NewGachaServiceServer(users, users, holder)
	u := &users.user
	u.Gem.FreeGem, u.Gem.PaidGem = 1_000_000, 1_000_000
	draw := func(step int32) (*pb.DrawResponse, error) {
		return srv.Draw(context.Background(), &pb.DrawRequest{
			GachaId: stepUpGachaId(entry, step), GachaPricePhaseId: entry.PricePhases[step-1].PhaseId, ExecCount: 1})
	}
	if got := shownStep(t, srv, entry); got != 1 {
		t.Fatalf("new summon shows step %d", got)
	}
	if _, err := draw(2); err == nil {
		t.Fatal("drew step 2 while on step 1")
	}
	for step := int32(1); step <= entry.MaxStepNumber; step++ {
		resp, err := draw(step)
		if err != nil {
			t.Fatalf("step %d: %v", step, err)
		}
		want := step%entry.MaxStepNumber + 1
		if next := resp.NextGacha.GetGachaModeStepupComposition(); next.StepNumber != want || next.CurrentStepNumber != want {
			t.Fatalf("after step %d the draw returns step %d (current %d)", step, next.StepNumber, next.CurrentStepNumber)
		}
		if got := shownStep(t, srv, entry); got != want {
			t.Fatalf("after step %d the summon shows step %d", step, got)
		}
	}
	if loops := u.Gacha.BannerStates[entry.GachaId].LoopCount; loops != 1 {
		t.Fatalf("loop count %d", loops)
	}
	// A save past the last step (summons once had more) starts again at 1.
	bs := u.Gacha.BannerStates[entry.GachaId]
	bs.StepNumber = entry.MaxStepNumber + 2
	u.Gacha.BannerStates[entry.GachaId] = bs
	if got := shownStep(t, srv, entry); got != 1 {
		t.Fatalf("a save past the last step shows step %d", got)
	}
	if _, err := draw(1); err != nil {
		t.Fatal(err)
	}
	if got := shownStep(t, srv, entry); got != 2 {
		t.Fatalf("after step 1 the summon shows step %d", got)
	}
}
