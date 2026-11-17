package questflow

import (
	"reflect"
	"testing"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
)

func TestBoostedHit(t *testing.T) {
	if !boostedHit(3, 0, listedRolls(t, 0)) || boostedHit(3, 0, listedRolls(t, 1)) {
		t.Fatal("no boost: roll(3) == 0 decides")
	}
	if !boostedHit(3, 500, listedRolls(t, 1499)) || boostedHit(3, 500, listedRolls(t, 1500)) {
		t.Fatal("+500‰ on 1 in 3: roll(3000) < 1500")
	}
	if !boostedHit(2, 1000, listedRolls(t)) {
		t.Fatal("+1000‰ on 1 in 2 is certain, with no roll")
	}
}

func TestBoostCountsGivesAChanceOfMore(t *testing.T) {
	half := func(model.PossessionType, int32) int64 { return 500 }
	got := boostCounts([]RewardGrant{{PossessionType: tMaterial, PossessionId: 1, Count: 2}}, half, listedRolls(t))
	if got[0].Count != 3 {
		t.Fatalf("count 2 at 500‰: %+v", got)
	}
	if got := boostCounts([]RewardGrant{{PossessionType: tMaterial, PossessionId: 1, Count: 1}}, half, listedRolls(t, 499)); got[0].Count != 2 {
		t.Fatalf("roll 499: %+v", got)
	}
	if got := boostCounts([]RewardGrant{{PossessionType: tMaterial, PossessionId: 1, Count: 1}}, half, listedRolls(t, 500)); got[0].Count != 1 {
		t.Fatalf("roll 500: %+v", got)
	}
	if got := boostCounts([]RewardGrant{{PossessionType: tMaterial, PossessionId: 1, Count: 1}}, nil, listedRolls(t)); got[0].Count != 1 {
		t.Fatalf("no boost: %+v", got)
	}
}

func dropRateHandler() *QuestHandler {
	h := testHandler()
	h.ImportantItemEffects = &masterdata.ImportantItemEffectCatalog{
		DropRates: []masterdata.ImportantItemDropRate{
			{ImportantItemId: 200011, GroupingId: 1, EndDatetime: 1000, RatePermil: 500, QuestGroupId: 101, ItemGroupId: 101},
			{ImportantItemId: 200018, GroupingId: 1, EndDatetime: 1000, RatePermil: 800, QuestGroupId: 101, ItemGroupId: 101},
			{ImportantItemId: 200021, GroupingId: 2, EndDatetime: 1000, RatePermil: 1000, QuestGroupId: 101, ItemGroupId: 0},
		},
		QuestGroups: map[int32][]masterdata.EntityMImportantItemEffectTargetQuestGroup{101: {
			{ImportantItemEffectTargetQuestGroupType: masterdata.ImportantItemTargetMainQuestChapterId, TargetValue: 2},
		}},
		ItemGroups: map[int32][]masterdata.EntityMImportantItemEffectTargetItemGroup{101: {{PossessionType: 5, PossessionId: 100001}}},
	}
	return h
}

func TestDropBoostOneGroupingTakesTheLargest(t *testing.T) {
	h := dropRateHandler()
	u := testUser()
	u.ImportantItems[200011], u.ImportantItems[200018], u.ImportantItems[200021] = 1, 1, 1
	main := campaign.QuestTarget{QuestId: testQuest, QuestType: campaign.QuestTypeMainQuest, ChapterId: 2}
	b := h.dropBoostFor(u, main, 0)
	if got := b(tMaterial, 100001); got != 1800 {
		t.Fatalf("targeted item: %d, want 800 + 1000", got)
	}
	if got := b(tMaterial, 7); got != 1000 {
		t.Fatalf("other item: %d, want 1000", got)
	}
}

func TestDropBoostSkipsUnownedAndOutOfDate(t *testing.T) {
	h := dropRateHandler()
	u := testUser()
	main := campaign.QuestTarget{QuestId: testQuest, QuestType: campaign.QuestTypeMainQuest, ChapterId: 2}
	if b := h.dropBoostFor(u, main, 0); b != nil && b(tMaterial, 100001) != 0 {
		t.Fatal("boost without owning an item")
	}
	u.ImportantItems[200021] = 1
	if b := h.dropBoostFor(u, main, 2000); b != nil && b(tMaterial, 100001) != 0 {
		t.Fatal("boost after the effect ended")
	}
	other := main
	other.ChapterId = 3
	if b := h.dropBoostFor(u, other, 0); b != nil && b(tMaterial, 100001) != 0 {
		t.Fatal("boost outside the target quests")
	}
}

func TestListedDropsBoosted(t *testing.T) {
	boost := func(model.PossessionType, int32) int64 { return 500 }
	c := testListedCatalog()
	c.Materials[10] = []masterdata.ListedMaterial{{MaterialId: 100001, Rarity: 10}}
	// 1 in 2 at +500‰: roll(2000) < 1500 hits; the count roll is unchanged.
	got := listedDrops(c, 10, nil, nil, double, listedRolls(t, 1499, 0), boost)
	want := []RewardGrant{{PossessionType: tMaterial, PossessionId: 100001, Count: 2}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

// A target item group names memoirs by one rank variant; a drop of another
// variant of the same memoir (group and rarity) is the same memoir: the rank
// is rolled when it is granted.
func TestDropBoostMatchesMemoirsByKind(t *testing.T) {
	saved := listedDropCatalog
	t.Cleanup(func() { listedDropCatalog = saved })
	listedDropCatalog = testListedCatalog
	h := testHandler()
	h.ImportantItemEffects = &masterdata.ImportantItemEffectCatalog{
		DropRates: []masterdata.ImportantItemDropRate{{ImportantItemId: 200019, GroupingId: 19, EndDatetime: 1000, RatePermil: 1000, QuestGroupId: 101, ItemGroupId: 1201}},
		QuestGroups: map[int32][]masterdata.EntityMImportantItemEffectTargetQuestGroup{101: {
			{ImportantItemEffectTargetQuestGroupType: masterdata.ImportantItemTargetMainQuestChapterId, TargetValue: 2},
		}},
		ItemGroups: map[int32][]masterdata.EntityMImportantItemEffectTargetItemGroup{1201: {{PossessionType: int32(tParts), PossessionId: 102}}},
	}
	c := testListedCatalog()
	c.Parts[102] = masterdata.PartsKind{Group: 1, Rarity: 10} // another rank of 101
	listedDropCatalog = func() masterdata.ListedDropCatalog { return c }
	u := testUser()
	u.ImportantItems[200019] = 1
	b := h.dropBoostFor(u, campaign.QuestTarget{QuestId: testQuest, QuestType: campaign.QuestTypeMainQuest, ChapterId: 2}, 0)
	if b == nil || b(tParts, 101) != 1000 {
		t.Fatal("memoir 101 is the same kind as the targeted 102")
	}
	if b(tParts, 201) != 0 {
		t.Fatal("memoir 201 is another group")
	}
	if b(tParts, 121) != 0 {
		t.Fatal("memoir 121 is another rarity")
	}
}
