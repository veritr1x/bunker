package questflow

import (
	"testing"

	"lunar-tear/server/internal/model"
)

func TestSpendableMedals(t *testing.T) {
	drops := spendableMedals([]RewardGrant{
		{PossessionType: model.PossessionTypeConsumableItem, PossessionId: 53, Count: 3},
		{PossessionType: model.PossessionTypeConsumableItem, PossessionId: 54, Count: 1},
		{PossessionType: model.PossessionTypeConsumableItem, PossessionId: 63, Count: 2},
		{PossessionType: model.PossessionTypeConsumableItem, PossessionId: 65, Count: 1},
		{PossessionType: model.PossessionTypeConsumableItem, PossessionId: 22, Count: 4},
		// Not a consumable item: id 53 here is something else.
		{PossessionType: model.PossessionTypeMaterial, PossessionId: 53, Count: 1},
	})
	want := []int32{22, 22, 29, 29, 22, 53}
	for i, d := range drops {
		if d.PossessionId != want[i] {
			t.Errorf("drop %d: id %d, want %d", i, d.PossessionId, want[i])
		}
	}
	if drops[0].Count != 3 || drops[2].Count != 2 {
		t.Errorf("counts changed: %+v", drops)
	}
}
