package questflow

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
)

// Scar and Sin's stories 2-4 all unlock on quest 61: clearing it opens all three.
func TestQuestClearUnlocksEveryStoryItOpens(t *testing.T) {
	h := testHandler()
	cond := func(story int32) masterdata.EntityMWeaponStoryReleaseConditionGroup {
		return masterdata.EntityMWeaponStoryReleaseConditionGroup{WeaponStoryReleaseConditionGroupId: 7, StoryIndex: story,
			WeaponStoryReleaseConditionType: int32(model.WeaponStoryReleaseConditionTypeQuestClear), ConditionValue: 61}
	}
	h.ReleaseConditionsByGroupId = map[int32][]masterdata.EntityMWeaponStoryReleaseConditionGroup{7: {cond(2), cond(3), cond(4)}}
	h.WeaponIdsByReleaseConditionGroupId = map[int32][]int32{7: {testWeapon}}
	u := testUser()
	h.grantWeaponStoryUnlocksForQuestScene(u, 61, model.QuestResultTypeFullResult, 1)
	if got := u.WeaponStories[testWeapon].ReleasedMaxStoryIndex; got != 4 {
		t.Fatalf("stories up to %d, want 4", got)
	}
}
