package store

import "lunar-tear/server/internal/model"

// CatchUpWeaponStories unlocks the stories of the user's weapons whose
// quests are already cleared. Stories unlock as quests are cleared or
// weapons obtained, so weapons owned before a fix to their conditions (the
// Arc 2 ★2 weapons' either-quest stories) would otherwise never get them.
// It reports whether any story was unlocked.
func (g *PossessionGranter) CatchUpWeaponStories(user *UserState, nowMillis int64) bool {
	changed := false
	seen := make(map[int32]bool)
	for _, w := range user.Weapons {
		if seen[w.WeaponId] {
			continue
		}
		seen[w.WeaponId] = true
		ref, ok := g.WeaponById[w.WeaponId]
		if !ok || ref.WeaponStoryReleaseConditionGroupId == 0 {
			continue
		}
		for _, cond := range g.ReleaseConditions[ref.WeaponStoryReleaseConditionGroupId] {
			if cond.WeaponStoryReleaseConditionType != model.WeaponStoryReleaseConditionTypeQuestClear {
				continue
			}
			if qs, ok := user.Quests[cond.ConditionValue]; ok && qs.QuestStateType == model.UserQuestStateTypeCleared {
				if grantWeaponStoryUnlock(user, w.WeaponId, cond.StoryIndex, nowMillis) {
					changed = true
				}
			}
		}
	}
	return changed
}
