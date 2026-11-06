package questflow

import (
	"os"
	"path/filepath"
	"testing"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/mods"
)

// Mods changes are in use at once in tests.
func init() { mods.Recheck = 0 }

func useMods(t *testing.T, body string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "mods.json")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	mods.SetPath(path)
	t.Cleanup(func() { mods.SetPath("") })
}

func drops() []RewardGrant {
	return []RewardGrant{
		{PossessionType: model.PossessionTypeConsumableItem, PossessionId: 1, Count: 2},
		{PossessionType: model.PossessionTypeFreeGem, Count: 5},
		{PossessionType: model.PossessionTypeParts, PossessionId: 3, Count: 1},
		{PossessionType: model.PossessionTypeCostume, PossessionId: 4, Count: 1},
		{PossessionType: model.PossessionTypeImportantItem, PossessionId: 5, Count: 1},
	}
}

func TestTheMultiplierScalesItemsGemsAndGoldOnly(t *testing.T) {
	useMods(t, `{"rewardMultiplier": 3}`)
	got := modScaleDrops(drops(), campaign.QuestTarget{QuestType: campaign.QuestTypeMainQuest})
	want := []int32{6, 15, 1, 1, 1}
	for i, d := range got {
		if d.Count != want[i] {
			t.Fatalf("drop %d (%v) = %d, want %d", i, d.PossessionType, d.Count, want[i])
		}
	}
	if g := modScaleGold(100); g != 300 {
		t.Fatalf("gold = %d", g)
	}
}

func TestDarkMemoryQuestsAndNoModKeepTheirRewards(t *testing.T) {
	useMods(t, `{"rewardMultiplier": 10}`)
	dark := campaign.QuestTarget{QuestType: campaign.QuestTypeEventQuest, EventQuestType: eventQuestTypeEndContents}
	for i, d := range modScaleDrops(drops(), dark) {
		if d.Count != drops()[i].Count {
			t.Fatalf("Dark Memory drop %d multiplied", i)
		}
	}
	useMods(t, `{}`)
	for i, d := range modScaleDrops(drops(), campaign.QuestTarget{}) {
		if d.Count != drops()[i].Count {
			t.Fatalf("drop %d multiplied with the mod off", i)
		}
	}
	if modScaleGold(100) != 100 {
		t.Fatal("gold multiplied with the mod off")
	}
}
