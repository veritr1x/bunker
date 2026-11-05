package questflow

import "lunar-tear/server/internal/model"

// eventMedalBase maps the medal variants two event chapters drop to the medal
// their exchange takes. Chapter 508 (Coffin of Repose) drops 53 and 54 but its
// shop 6005 takes 22; chapter 513 (Rhythm's Citadel) drops 63, 64 and 65 but
// its shop 6010 takes 29. No open shop takes the variants (6030, which does,
// has no chapter linking to it), so as dropped they cannot be spent.
// The same mapping as the Lunar Tear Comfort Mod by NavHobbyDev (MIT).
var eventMedalBase = map[int32]int32{53: 22, 54: 22, 63: 29, 64: 29, 65: 29}

// spendableMedals turns those variants in a quest's drops into the medal the
// event's shop takes, one for one.
func spendableMedals(drops []RewardGrant) []RewardGrant {
	for i, d := range drops {
		if d.PossessionType != model.PossessionTypeConsumableItem {
			continue
		}
		if base, ok := eventMedalBase[d.PossessionId]; ok {
			drops[i].PossessionId = base
		}
	}
	return drops
}
