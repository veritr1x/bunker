package questflow

// Pod Programs > Mods: the reward multiplier (from the Lunar Tear Comfort Mod
// by NavHobbyDev, MIT). A finished or skipped quest's drops and gold are
// multiplied. What stays as it is: Dark Memory quests, memoirs, costumes,
// weapons, companions, important items, and limit-break and awakening
// materials (things the game gives one at a time on purpose). The drops are
// multiplied before they are granted, so the result screen shows what arrives.

import (
	"lunar-tear/server/internal/bunkercache"
	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/mods"
	"lunar-tear/server/internal/utils"
)

// eventQuestTypeEndContents is an event chapter of Dark Memory quests.
const eventQuestTypeEndContents = 7

// Material types kept at one: weapon and costume limit breaks and awakenings.
var unmultipliedMaterialTypes = map[int32]bool{80: true, 90: true, 110: true, 130: true}

var unmultipliedMaterials = bunkercache.Value(func() map[int32]bool {
	out := map[int32]bool{}
	if rows, err := utils.ReadTable[masterdata.EntityMMaterial]("m_material"); err == nil {
		for _, m := range rows {
			if unmultipliedMaterialTypes[m.MaterialType] {
				out[m.MaterialId] = true
			}
		}
	}
	return out
})

// modMultiplies reports whether the reward multiplier applies to a drop.
func modMultiplies(possessionType model.PossessionType, possessionId int32) bool {
	switch possessionType {
	case model.PossessionTypeConsumableItem, model.PossessionTypeFreeGem:
		return true
	case model.PossessionTypeMaterial:
		return !unmultipliedMaterials()[possessionId]
	}
	return false
}

// modScaleDrops multiplies a quest's drops (see modMultiplies).
func modScaleDrops(drops []RewardGrant, target campaign.QuestTarget) []RewardGrant {
	m := mods.Get().Multiplier()
	if m <= 1 || target.QuestType == campaign.QuestTypeEventQuest && target.EventQuestType == eventQuestTypeEndContents {
		return drops
	}
	for i := range drops {
		if modMultiplies(drops[i].PossessionType, drops[i].PossessionId) {
			drops[i].Count *= m
		}
	}
	return drops
}

// modScaleGold multiplies a quest's gold.
func modScaleGold(gold int32) int32 {
	return gold * mods.Get().Multiplier()
}
