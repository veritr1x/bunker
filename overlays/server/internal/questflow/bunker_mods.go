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
	"lunar-tear/server/internal/gametime"
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

// newDayPaused reports whether Start a new day was pressed on the game day of
// now, which pauses the challenge bonus (gametime.NewDayPausesBonus).
var newDayPaused = gametime.NewDayPausesBonus

// rewardFactor multiplies a quest's drops and gold: the reward multiplier, or
// with no comfort mods on, the challenge bonus.
func rewardFactor() int32 {
	return mods.Get().RewardFactor(newDayPaused(gametime.NowMillis()))
}

// modDailyClears is how many of n clears count against a quest's daily
// limit: none with Unlimited daily plays.
func modDailyClears(n int32) int32 {
	if mods.Get().UnlimitedDailyPlays {
		return 0
	}
	return n
}

// modSkipTickets is how many skip tickets n skips use: none with Free skips.
func modSkipTickets(n int32) int32 {
	if mods.Get().FreeSkips {
		return 0
	}
	return n
}

// modScaleExp multiplies the EXP a quest gives (the EXP multiplier).
func modScaleExp(exp int32) int32 {
	return exp * mods.Get().ExpFactor()
}

// modScaleDrops multiplies a quest's drops (see modMultiplies).
func modScaleDrops(drops []RewardGrant, target campaign.QuestTarget) []RewardGrant {
	m := rewardFactor()
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
	return gold * rewardFactor()
}
