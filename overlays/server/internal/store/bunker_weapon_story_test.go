package store

import (
	"testing"

	"lunar-tear/server/internal/model"
)

// Weapons owned before a fix to their stories' conditions get the stories
// whose quests are already cleared.
func TestCatchUpWeaponStories(t *testing.T) {
	clear := func(story, quest int32) WeaponStoryReleaseCond {
		return WeaponStoryReleaseCond{StoryIndex: story, WeaponStoryReleaseConditionType: model.WeaponStoryReleaseConditionTypeQuestClear, ConditionValue: quest}
	}
	g := &PossessionGranter{
		WeaponById: map[int32]WeaponRef{101181: {WeaponStoryReleaseConditionGroupId: 17}, 101001: {WeaponStoryReleaseConditionGroupId: 2}},
		ReleaseConditions: map[int32][]WeaponStoryReleaseCond{
			17: {{StoryIndex: 1, WeaponStoryReleaseConditionType: model.WeaponStoryReleaseConditionTypeAcquisition}, clear(2, 344), clear(2, 444), clear(3, 347), clear(3, 447)},
			2:  {clear(2, 5)},
		},
	}
	u := SeedUserState(1, "u", 0, model.DefaultPlatform)
	u.Weapons["w1"] = WeaponState{UserWeaponUuid: "w1", WeaponId: 101181}
	u.Weapons["w2"] = WeaponState{UserWeaponUuid: "w2", WeaponId: 101001}
	u.Quests[444] = UserQuestState{QuestId: 444, QuestStateType: model.UserQuestStateTypeCleared}
	u.Quests[347] = UserQuestState{QuestId: 347, QuestStateType: model.UserQuestStateTypeActive}
	if !g.CatchUpWeaponStories(u, 1) {
		t.Fatal("nothing caught up")
	}
	if got := u.WeaponStories[101181].ReleasedMaxStoryIndex; got != 2 {
		t.Fatalf("Ebony's stories up to %d, want 2", got)
	}
	if _, ok := u.WeaponStories[101001]; ok {
		t.Fatal("story granted for an uncleared quest")
	}
	if g.CatchUpWeaponStories(u, 2) {
		t.Fatal("caught up twice")
	}
}
