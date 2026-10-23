package masterdata

import (
	"log"
	"sort"

	"lunar-tear/server/internal/utils"
)

// conditionOperationOr is ConditionOperationType.OR in the client.
const conditionOperationOr = 2

// withWeaponStoryOperations reads the operation tables that some weapon
// stories' conditions point to and expands them; see
// expandWeaponStoryOperations.
func withWeaponStoryOperations(rows []EntityMWeaponStoryReleaseConditionGroup) []EntityMWeaponStoryReleaseConditionGroup {
	groups, err := utils.ReadTable[EntityMWeaponStoryReleaseConditionOperationGroup]("m_weapon_story_release_condition_operation_group")
	if err != nil {
		log.Printf("[WeaponStory] operation groups: %v", err)
		return rows
	}
	ops, err := utils.ReadTable[EntityMWeaponStoryReleaseConditionOperation]("m_weapon_story_release_condition_operation")
	if err != nil {
		log.Printf("[WeaponStory] operations: %v", err)
		return rows
	}
	return expandWeaponStoryOperations(rows, groups, ops)
}

// expandWeaponStoryOperations turns a story condition that names an
// operation group instead of a value (the Arc 2 ★2 weapons: "clear quest 344
// or 444") into one condition per alternative, so a story unlocks when any
// of them is met. Every-of groups can't be written that way and are left out
// (the game data has none).
func expandWeaponStoryOperations(rows []EntityMWeaponStoryReleaseConditionGroup,
	groups []EntityMWeaponStoryReleaseConditionOperationGroup,
	ops []EntityMWeaponStoryReleaseConditionOperation) []EntityMWeaponStoryReleaseConditionGroup {
	opType := make(map[int32]int32, len(groups))
	for _, g := range groups {
		opType[g.WeaponStoryReleaseConditionOperationGroupId] = g.ConditionOperationType
	}
	byGroup := make(map[int32][]EntityMWeaponStoryReleaseConditionOperation)
	for _, op := range ops {
		byGroup[op.WeaponStoryReleaseConditionOperationGroupId] = append(byGroup[op.WeaponStoryReleaseConditionOperationGroupId], op)
	}
	out := make([]EntityMWeaponStoryReleaseConditionGroup, 0, len(rows))
	for _, r := range rows {
		id := r.WeaponStoryReleaseConditionOperationGroupId
		if id == 0 {
			out = append(out, r)
			continue
		}
		if opType[id] != conditionOperationOr {
			log.Printf("[WeaponStory] condition group %d story %d: operation group %d (type %d) left out",
				r.WeaponStoryReleaseConditionGroupId, r.StoryIndex, id, opType[id])
			continue
		}
		alts := byGroup[id]
		sort.Slice(alts, func(i, j int) bool { return alts[i].SortOrder < alts[j].SortOrder })
		for _, op := range alts {
			out = append(out, EntityMWeaponStoryReleaseConditionGroup{
				WeaponStoryReleaseConditionGroupId: r.WeaponStoryReleaseConditionGroupId,
				StoryIndex:                         r.StoryIndex,
				WeaponStoryReleaseConditionType:    op.WeaponStoryReleaseConditionType,
				ConditionValue:                     op.ConditionValue,
			})
		}
	}
	return out
}
