package questflow

import (
	"reflect"
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
)

const (
	tMaterial = model.PossessionTypeMaterial
	tParts    = model.PossessionTypeParts
)

func testListedCatalog() masterdata.ListedDropCatalog {
	set := []int32{1, 2, 3}
	return masterdata.ListedDropCatalog{
		Materials: map[int32][]masterdata.ListedMaterial{
			10: {{MaterialId: 100001, Rarity: 10}, {MaterialId: 300001, Rarity: 30}, {MaterialId: 401001, Rarity: 10}, {MaterialId: 555, Rarity: 0}},
		},
		Parts: map[int32]masterdata.PartsKind{
			101: {Group: 1, Rarity: 10}, 201: {Group: 2, Rarity: 10}, 301: {Group: 3, Rarity: 10},
			121: {Group: 1, Rarity: 20}, 221: {Group: 2, Rarity: 20}, 321: {Group: 3, Rarity: 20},
		},
		SetOf: map[int32][]int32{1: set, 2: set, 3: set},
		PartsFor: map[masterdata.PartsKind]int32{
			{Group: 1, Rarity: 10}: 101, {Group: 2, Rarity: 10}: 201, {Group: 3, Rarity: 10}: 301,
			{Group: 1, Rarity: 20}: 121, {Group: 2, Rarity: 20}: 221, {Group: 3, Rarity: 20}: 321,
		},
	}
}

func listedRolls(t *testing.T, values ...int64) func(int64) int64 {
	t.Cleanup(func() {
		if len(values) != 0 {
			t.Errorf("%d rolls left unused: %v", len(values), values)
		}
	})
	return func(n int64) int64 {
		if len(values) == 0 {
			t.Fatalf("unexpected roll in [0, %d)", n)
		}
		v := values[0]
		values = values[1:]
		if v >= n {
			t.Fatalf("roll %d out of [0, %d)", v, n)
		}
		return v
	}
}

func double(n int32) int32 { return 2 * n }

func TestListedMaterialsRollByRarity(t *testing.T) {
	granted := []RewardGrant{{PossessionType: tMaterial, PossessionId: 401001, Count: 2}}
	got := listedDrops(testListedCatalog(), 10, nil, granted, double, listedRolls(t, 0, 1, 0), nil)
	want := []RewardGrant{{PossessionType: tMaterial, PossessionId: 100001, Count: 4}, {PossessionType: tMaterial, PossessionId: 300001, Count: 2}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

func TestListedMaterialsSkipShownAtAnyCount(t *testing.T) {
	shown := []RewardGrant{{PossessionType: tMaterial, PossessionId: 100001, Count: 7}}
	granted := []RewardGrant{{PossessionType: tMaterial, PossessionId: 401001, Count: 1}}
	if got := listedDrops(testListedCatalog(), 10, shown, granted, double, listedRolls(t, 4), nil); len(got) != 0 {
		t.Fatalf("got %+v", got)
	}
}

func TestListedMemoirsCompleteTheShownSet(t *testing.T) {
	shown := []RewardGrant{{PossessionType: tParts, PossessionId: 101, Count: 1}, {PossessionType: tParts, PossessionId: 221, Count: 1}}
	got := listedDrops(testListedCatalog(), 11, shown, shown, double, listedRolls(t, 0, 1, 2, 0), nil)
	want := []RewardGrant{{PossessionType: tParts, PossessionId: 201, Count: 2}, {PossessionType: tParts, PossessionId: 321, Count: 2}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

// The chapter-memoir rule may already have granted a piece (139 quest/memoir
// pairs overlap in the game's data): it isn't rolled a second time.
func TestListedMemoirsSkipAPieceAlreadyGranted(t *testing.T) {
	shown := []RewardGrant{{PossessionType: tParts, PossessionId: 101, Count: 1}}
	granted := append(append([]RewardGrant{}, shown...), RewardGrant{PossessionType: tParts, PossessionId: 202, Count: 1})
	c := testListedCatalog()
	c.Parts[202] = masterdata.PartsKind{Group: 2, Rarity: 10} // another rank of group 2 at rarity 10
	got := listedDrops(c, 11, shown, granted, double, listedRolls(t, 0), nil)
	want := []RewardGrant{{PossessionType: tParts, PossessionId: 301, Count: 2}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

func TestListedMemoirsFullSetAddsNothing(t *testing.T) {
	shown := []RewardGrant{{PossessionType: tParts, PossessionId: 101}, {PossessionType: tParts, PossessionId: 201}, {PossessionType: tParts, PossessionId: 301}}
	if got := listedDrops(testListedCatalog(), 11, shown, shown, double, listedRolls(t), nil); len(got) != 0 {
		t.Fatalf("got %+v", got)
	}
}

func TestListedDropsForUsesTheOriginalQuest(t *testing.T) {
	saved := listedDropCatalog
	t.Cleanup(func() { listedDropCatalog = saved })
	listedDropCatalog = testListedCatalog
	got := listedDropsFor(1_000_000_010, nil, nil, double, listedRolls(t, 0, 1, 0, 1), nil)
	want := []RewardGrant{{PossessionType: tMaterial, PossessionId: 100001, Count: 4}, {PossessionType: tMaterial, PossessionId: 300001, Count: 2}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

func TestListedMemoirsCompleteChapterScreenSets(t *testing.T) {
	c := testListedCatalog()
	c.ChapterShown = map[int32][]int32{11: {121}}
	// The screen's piece itself still rolls when the chapter memoirs didn't
	// grant it this clear: g1 (hit), g2 (hit), g3 (miss).
	got := listedDrops(c, 11, nil, nil, double, listedRolls(t, 0, 0, 1), nil)
	want := []RewardGrant{{PossessionType: tParts, PossessionId: 121, Count: 2}, {PossessionType: tParts, PossessionId: 221, Count: 2}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

func TestListedChapterScreenPieceGrantedIsNotRolledAgain(t *testing.T) {
	c := testListedCatalog()
	c.ChapterShown = map[int32][]int32{11: {121}}
	granted := []RewardGrant{{PossessionType: tParts, PossessionId: 121, Count: 1}}
	got := listedDrops(c, 11, nil, granted, double, listedRolls(t, 1, 0), nil)
	want := []RewardGrant{{PossessionType: tParts, PossessionId: 321, Count: 2}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

func dungeonCatalog() masterdata.ListedDropCatalog {
	c := testListedCatalog()
	for g, base := range map[int32]int32{1: 100, 2: 200, 3: 300} {
		for _, r := range []int32{30, 40} {
			id := base + r + 1
			c.Parts[id] = masterdata.PartsKind{Group: g, Rarity: r}
			c.PartsFor[masterdata.PartsKind{Group: g, Rarity: r}] = id
		}
	}
	c.Dungeon = map[int32]bool{12: true}
	return c
}

func TestListedDungeonRollsHigherRarities(t *testing.T) {
	shown := []RewardGrant{{PossessionType: tParts, PossessionId: 121, Count: 1}}
	got := listedDrops(dungeonCatalog(), 12, shown, shown, double, listedRolls(t, 1, 1, 0, 9, 9, 29, 0, 29), nil)
	want := []RewardGrant{{PossessionType: tParts, PossessionId: 131, Count: 2}, {PossessionType: tParts, PossessionId: 241, Count: 2}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

func TestListedDungeonTopRaritySetRollsNothingHigher(t *testing.T) {
	shown := []RewardGrant{{PossessionType: tParts, PossessionId: 141}, {PossessionType: tParts, PossessionId: 241}, {PossessionType: tParts, PossessionId: 341}}
	if got := listedDrops(dungeonCatalog(), 12, shown, shown, double, listedRolls(t), nil); len(got) != 0 {
		t.Fatalf("got %+v", got)
	}
}

func TestListedNotADungeonRollsNoHigherRarity(t *testing.T) {
	c := dungeonCatalog()
	c.Dungeon = nil
	shown := []RewardGrant{{PossessionType: tParts, PossessionId: 121, Count: 1}}
	if got := listedDrops(c, 12, shown, shown, double, listedRolls(t, 1, 1), nil); len(got) != 0 {
		t.Fatalf("got %+v", got)
	}
}

// A dungeon's chapter screen may show a set's 4★ piece; the 3★ in between
// still rolls, stepping up from the quest's own drops, and the 4★ pieces are
// rolled once, by the set completion.
func TestListedDungeonStepsUpFromItsOwnDrops(t *testing.T) {
	c := dungeonCatalog()
	c.ChapterShown = map[int32][]int32{12: {141}}
	shown := []RewardGrant{{PossessionType: tParts, PossessionId: 121, Count: 1}}
	// Completion: r20 g2, g3 miss; r40 (the screen's) g1, g2, g3 miss.
	// Dungeon from r20: r30 g1, g2 (hit), g3; r40 is the completion's already.
	got := listedDrops(c, 12, shown, shown, double, listedRolls(t, 1, 1, 1, 1, 1, 9, 0, 9), nil)
	want := []RewardGrant{{PossessionType: tParts, PossessionId: 231, Count: 2}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}
