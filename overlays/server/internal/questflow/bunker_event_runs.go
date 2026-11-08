package questflow

import (
	"log"
	"sync"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// Bunker: a rerun event's earlier runs pay their own drops and quest bonuses
// (masterdata.EventRuns): with the Original calendar each run is a chapter
// copy carrying its run's link, and a quest finished in it drops the medal it
// dropped then, not the last run's. Replaced in tests.
var eventRunsOf = masterdata.EventRuns

// chapterLinkOf is the link the active game data gives an event chapter.
var chapterLinkOf = func(h *QuestHandler, chapterId int32) int32 {
	return chapterLinks(h.QuestCatalog)[chapterId]
}

var (
	chapterLinksMu    sync.Mutex
	chapterLinksCache = map[*masterdata.QuestCatalog]map[int32]int32{}
)

// chapterLinks reads m_event_quest_chapter's links once per loaded catalog
// (a reload builds a new catalog).
func chapterLinks(cat *masterdata.QuestCatalog) map[int32]int32 {
	chapterLinksMu.Lock()
	defer chapterLinksMu.Unlock()
	if links, ok := chapterLinksCache[cat]; ok {
		return links
	}
	links := map[int32]int32{}
	rows, err := utils.ReadTable[masterdata.EntityMEventQuestChapter]("m_event_quest_chapter")
	if err != nil {
		log.Printf("[EventRuns] read m_event_quest_chapter: %v", err)
	}
	for _, r := range rows {
		links[r.EventQuestChapterId] = r.EventQuestLinkId
	}
	chapterLinksCache = map[*masterdata.QuestCatalog]map[int32]int32{cat: links}
	return links
}

// eventRun is the earlier run an event chapter replays, or nil.
func (h *QuestHandler) eventRun(chapterId int32) *masterdata.EventRun {
	if chapterId == 0 {
		return nil
	}
	return eventRunsOf().For(chapterId, chapterLinkOf(h, chapterId))
}

// pickupDrops is a clear's pickup drops: an earlier run's own, else the quest's
// pickup reward group.
func (h *QuestHandler) pickupDrops(questDef masterdata.EntityMQuest, target campaign.QuestTarget, dropRate campaign.DropRateMul) []RewardGrant {
	var drops []RewardGrant
	if target.QuestType == campaign.QuestTypeEventQuest {
		if run := h.eventRun(target.ChapterId); run != nil {
			if own, ok := run.Drops[questDef.QuestId]; ok {
				for _, d := range own {
					drops = append(drops, RewardGrant{PossessionType: model.PossessionType(d[0]), PossessionId: d[1], Count: dropRate.Apply(d[2])})
				}
				return drops
			}
		}
	}
	if questDef.QuestPickupRewardGroupId != 0 {
		for _, dropId := range h.PickupRewardIdsByGroupId[questDef.QuestPickupRewardGroupId] {
			if bdr, ok := h.BattleDropRewardById[dropId]; ok {
				drops = append(drops, RewardGrant{
					PossessionType: model.PossessionType(bdr.PossessionType),
					PossessionId:   bdr.PossessionId,
					Count:          dropRate.Apply(bdr.Count),
				})
			}
		}
	}
	return drops
}

// runBonusDrops is a deck's quest bonus payouts in an earlier run, as
// questBonusDrops resolves them: each character's, the best costume and weapon
// rule each piece's limit break reaches. ok is false outside an earlier run.
func (h *QuestHandler) runBonusDrops(user *store.UserState, questDef masterdata.EntityMQuest, deck store.DeckState) (out []RewardGrant, ok bool) {
	if user.EventQuest.CurrentQuestId != questDef.QuestId {
		return nil, false
	}
	run := h.eventRun(user.EventQuest.CurrentEventQuestChapterId)
	if run == nil {
		return nil, false
	}
	rules := run.BonusRules(questDef.QuestId)
	pay := func(r masterdata.EventRunBonusRule) {
		for _, p := range r.Pays {
			out = append(out, RewardGrant{PossessionType: model.PossessionType(p[0]), PossessionId: p[1], Count: p[2]})
		}
	}
	best := func(kind string, id, limitBreak int32) {
		var found *masterdata.EventRunBonusRule
		for i := range rules {
			r := &rules[i]
			if r.Kind == kind && r.Id == id && r.LimitBreak <= limitBreak && (found == nil || r.LimitBreak > found.LimitBreak) {
				found = r
			}
		}
		if found != nil {
			pay(*found)
		}
	}
	for _, dcUuid := range deckCharacterUuids(deck) {
		dc, ok := user.DeckCharacters[dcUuid]
		if !ok {
			continue
		}
		if co, ok := user.Costumes[dc.UserCostumeUuid]; ok {
			if cm, ok := h.CostumeById[co.CostumeId]; ok {
				for _, r := range rules {
					if r.Kind == "character" && r.Id == cm.CharacterId {
						pay(r)
					}
				}
			}
			best("costume", co.CostumeId, co.LimitBreakCount)
		}
		for _, wUuid := range append([]string{dc.MainUserWeaponUuid}, user.DeckSubWeapons[dcUuid]...) {
			if w, ok := user.Weapons[wUuid]; ok {
				best("weapon", w.WeaponId, w.LimitBreakCount)
			}
		}
	}
	return out, true
}
