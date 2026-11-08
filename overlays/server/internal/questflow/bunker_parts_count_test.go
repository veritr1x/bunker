package questflow

import (
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// A memoir drop grants its Count: a drop-rate campaign rounds a Count of 1 up
// to 2, and the reward popup shows 2.
func TestPartsDropGrantsItsCount(t *testing.T) {
	h := &QuestHandler{Granter: &store.PossessionGranter{}}
	u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	h.grantDropRewards(u, []RewardGrant{
		{PossessionType: model.PossessionTypeParts, PossessionId: 999001, Count: 2},
		{PossessionType: model.PossessionTypeParts, PossessionId: 999002, Count: 0},
	}, nil, nil, 1)
	byId := map[int32]int{}
	for _, p := range u.Parts {
		byId[p.PartsId]++
	}
	if byId[999001] != 2 || byId[999002] != 1 {
		t.Fatalf("parts granted %v, want 2 of 999001 and 1 of 999002", byId)
	}
}
