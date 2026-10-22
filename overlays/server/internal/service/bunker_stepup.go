package service

import (
	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/gacha"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// The client builds a multi-step summon from one Gacha per step, grouped by
// GachaStepGroupId: it shows the one whose StepNumber is CurrentStepNumber
// (CalculatorGacha.CreateStepupDataGacha) and gets nothing to show when no
// such step is sent. Step 1 keeps the summon's id; step n > 1 is
// stepUpGachaIdBase + id*10 + n.
const stepUpGachaIdBase int32 = 1_000_000_000

func stepUpGachaId(entry store.GachaCatalogEntry, step int32) int32 {
	if step <= 1 {
		return entry.GachaId
	}
	return stepUpGachaIdBase + entry.GachaId*10 + step
}

// stepUpCurrent is the step the player is on (see gacha.CurrentStep).
func stepUpCurrent(entry store.GachaCatalogEntry, bs *store.GachaBannerState) int32 {
	if bs == nil {
		return 1
	}
	return gacha.CurrentStep(entry, *bs)
}

// resolveGachaId finds the summon a client gacha id stands for, and the step
// for a step id (0 otherwise).
func resolveGachaId(catalog []store.GachaCatalogEntry, gachaId int32) (*store.GachaCatalogEntry, int32) {
	id, step := gachaId, int32(0)
	if gachaId > stepUpGachaIdBase {
		id, step = (gachaId-stepUpGachaIdBase)/10, (gachaId-stepUpGachaIdBase)%10
	}
	if box, _, ok := masterdata.EventSummonFor(gachaId); ok {
		id = box.Base // an event summon's level
	}
	for i := range catalog {
		e := &catalog[i]
		if e.GachaId != id {
			continue
		}
		if step != 0 && (e.GachaModeType != model.GachaModeStepup || step > e.MaxStepNumber) {
			return nil, 0
		}
		return e, step
	}
	return nil, 0
}

// stepUpGacha is the Gacha for one step: its own id, step number and price.
func stepUpGacha(entry store.GachaCatalogEntry, bs *store.GachaBannerState, user store.UserState, step int32) *pb.Gacha {
	g := toProtoGachaFor(entry, bs, user)
	g.GachaId = stepUpGachaId(entry, step)
	if mode, ok := g.GachaMode.(*pb.Gacha_GachaModeStepupComposition); ok {
		mode.GachaModeStepupComposition.StepNumber = step
	}
	phases := g.GachaPricePhase[:0]
	for i, p := range g.GachaPricePhase {
		if entry.PricePhases[i].StepNumber == step {
			phases = append(phases, p)
		}
	}
	g.GachaPricePhase = phases
	return g
}

// protoGachas is a summon as the client lists it: one Gacha, or one per step.
func protoGachas(entry store.GachaCatalogEntry, bs *store.GachaBannerState, user store.UserState) []*pb.Gacha {
	if box, _, ok := masterdata.EventSummonFor(entry.GachaId); ok {
		return eventSummonGachas(entry, box, bs, user)
	}
	if entry.GachaModeType != model.GachaModeStepup || entry.MaxStepNumber < 1 {
		return []*pb.Gacha{toProtoGachaFor(entry, bs, user)}
	}
	out := make([]*pb.Gacha, 0, entry.MaxStepNumber)
	for step := int32(1); step <= entry.MaxStepNumber; step++ {
		out = append(out, stepUpGacha(entry, bs, user, step))
	}
	return out
}

// protoGachaById is the Gacha the client asked for by id: the step it names,
// or for a multi-step summon's own id, step 1.
func protoGachaById(entry store.GachaCatalogEntry, step int32, bs *store.GachaBannerState, user store.UserState) *pb.Gacha {
	if box, _, ok := masterdata.EventSummonFor(entry.GachaId); ok {
		gs := eventSummonGachas(entry, box, bs, user)
		return gs[min(int(gacha.EventLevel(derefState(bs))), len(gs))-1]
	}
	if entry.GachaModeType != model.GachaModeStepup || entry.MaxStepNumber < 1 {
		return toProtoGachaFor(entry, bs, user)
	}
	return stepUpGacha(entry, bs, user, max(step, 1))
}

func derefState(bs *store.GachaBannerState) store.GachaBannerState {
	if bs == nil {
		return store.GachaBannerState{}
	}
	return *bs
}
