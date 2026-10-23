package masterdata

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"lunar-tear/server/internal/masterdata/memorydb"
	"lunar-tear/server/internal/model"
)

func TestWeaponStoryEitherQuestBecomesOneConditionPerQuest(t *testing.T) {
	rows := []EntityMWeaponStoryReleaseConditionGroup{
		{WeaponStoryReleaseConditionGroupId: 17, StoryIndex: 1, WeaponStoryReleaseConditionType: 1},
		{WeaponStoryReleaseConditionGroupId: 17, StoryIndex: 2, WeaponStoryReleaseConditionType: 6, WeaponStoryReleaseConditionOperationGroupId: 171},
		{WeaponStoryReleaseConditionGroupId: 2, StoryIndex: 2, WeaponStoryReleaseConditionType: 6, ConditionValue: 5},
	}
	groups := []EntityMWeaponStoryReleaseConditionOperationGroup{
		{WeaponStoryReleaseConditionOperationGroupId: 171, ConditionOperationType: conditionOperationOr},
	}
	ops := []EntityMWeaponStoryReleaseConditionOperation{
		{WeaponStoryReleaseConditionOperationGroupId: 171, SortOrder: 2, WeaponStoryReleaseConditionType: 6, ConditionValue: 444},
		{WeaponStoryReleaseConditionOperationGroupId: 171, SortOrder: 1, WeaponStoryReleaseConditionType: 6, ConditionValue: 344},
	}
	got := expandWeaponStoryOperations(rows, groups, ops)
	want := []EntityMWeaponStoryReleaseConditionGroup{
		rows[0],
		{WeaponStoryReleaseConditionGroupId: 17, StoryIndex: 2, WeaponStoryReleaseConditionType: 6, ConditionValue: 344},
		{WeaponStoryReleaseConditionGroupId: 17, StoryIndex: 2, WeaponStoryReleaseConditionType: 6, ConditionValue: 444},
		rows[2],
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v\nwant %+v", got, want)
	}
}

// Every-quest groups can't be one condition per quest; the game data has none.
func TestWeaponStoryEveryQuestGroupIsLeftOut(t *testing.T) {
	rows := []EntityMWeaponStoryReleaseConditionGroup{
		{WeaponStoryReleaseConditionGroupId: 9, StoryIndex: 2, WeaponStoryReleaseConditionType: 6, WeaponStoryReleaseConditionOperationGroupId: 91},
	}
	groups := []EntityMWeaponStoryReleaseConditionOperationGroup{{WeaponStoryReleaseConditionOperationGroupId: 91, ConditionOperationType: 1}}
	ops := []EntityMWeaponStoryReleaseConditionOperation{{WeaponStoryReleaseConditionOperationGroupId: 91, SortOrder: 1, WeaponStoryReleaseConditionType: 6, ConditionValue: 1}}
	if got := expandWeaponStoryOperations(rows, groups, ops); len(got) != 0 {
		t.Fatalf("every-quest group became %+v", got)
	}
}

// Ebony (Marie's ★2 weapon, group 17) unlocks story 2 on quest 344 or 444.
func TestEbonyStoriesUnlockOnEitherQuest(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	path := filepath.Join(t.TempDir(), "master.bin.e")
	data, err := os.ReadFile(master)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := memorydb.Init(path); err != nil {
		t.Fatal(err)
	}
	parts, err := LoadPartsCatalog()
	if err != nil {
		t.Fatal(err)
	}
	cat, err := LoadQuestCatalog(parts)
	if err != nil {
		t.Fatal(err)
	}
	quests := map[int32][]int32{}
	for _, c := range cat.ReleaseConditionsByGroupId[17] {
		if model.WeaponStoryReleaseConditionType(c.WeaponStoryReleaseConditionType) == model.WeaponStoryReleaseConditionTypeQuestClear {
			quests[c.StoryIndex] = append(quests[c.StoryIndex], c.ConditionValue)
		}
	}
	want := map[int32][]int32{2: {344, 444}, 3: {347, 447}, 4: {350, 450}}
	if !reflect.DeepEqual(quests, want) {
		t.Fatalf("Ebony's story quests %v, want %v", quests, want)
	}
}
