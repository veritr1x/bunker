package questflow

import (
	"testing"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Chapter 510's first run dropped medal 25 and its bonuses paid it; the
// final game data (the last run) drops medal 149.
const runQuest, runChapter, runLink = int32(200271), int32(510), int32(17 + 100*10_000_000)

func eventRunHandler(t *testing.T, chapterLink int32) *QuestHandler {
	t.Helper()
	table, err := masterdata.ParseEventRuns([]byte(`{"copy_step":10000000,"chapters":{"510":[
	 {"link":17,"drops":{"200271":[[6,25,9],[5,100002,4]]},"bonus":{"200271":"b0"},
	  "bonuses":{"b0":[["character",1001,0,[[6,25,2]]],["costume",21001,1,[[6,25,3]]],["weapon",300,2,[[6,25,5]]],["weapon",300,4,[[6,25,8]]]]}},
	 null]}}`))
	if err != nil {
		t.Fatal(err)
	}
	saved := eventRunsOf
	eventRunsOf = func() *masterdata.EventRunTable { return table }
	savedLink := chapterLinkOf
	chapterLinkOf = func(*QuestHandler, int32) int32 { return chapterLink }
	t.Cleanup(func() { eventRunsOf, chapterLinkOf = saved, savedLink })
	cat := &masterdata.QuestCatalog{
		QuestById:                map[int32]masterdata.EntityMQuest{runQuest: {QuestId: runQuest, QuestPickupRewardGroupId: 1, QuestBonusId: 0}},
		PickupRewardIdsByGroupId: map[int32][]int32{1: {11}},
		BattleDropRewardById:     map[int32]masterdata.EntityMBattleDropReward{11: {BattleDropRewardId: 11, PossessionType: 6, PossessionId: 149, Count: 9}},
		CostumeById:              map[int32]masterdata.EntityMCostume{21001: {CostumeId: 21001, CharacterId: 1001}},
	}
	return &QuestHandler{QuestCatalog: cat, Config: &masterdata.GameConfig{}, Granter: &store.PossessionGranter{}}
}

func medals(drops []RewardGrant) map[int32]int32 {
	out := map[int32]int32{}
	for _, d := range drops {
		if d.PossessionType == model.PossessionTypeConsumableItem {
			out[d.PossessionId] += d.Count
		}
	}
	return out
}

func TestAnEarlierRunDropsItsOwnMedal(t *testing.T) {
	h := eventRunHandler(t, runLink)
	target := campaign.QuestTarget{QuestId: runQuest, QuestType: campaign.QuestTypeEventQuest, ChapterId: runChapter}
	got := medals(h.pickupDrops(h.QuestById[runQuest], target, campaign.DropRateMul{}))
	if got[25] != 9 || got[149] != 0 {
		t.Fatalf("medals %v, want 9 of medal 25 and none of 149", got)
	}
}

func TestTheFinalGameDataDropsItsMedal(t *testing.T) {
	h := eventRunHandler(t, 84) // the calendar off: the chapter keeps the final link
	target := campaign.QuestTarget{QuestId: runQuest, QuestType: campaign.QuestTypeEventQuest, ChapterId: runChapter}
	if got := medals(h.pickupDrops(h.QuestById[runQuest], target, campaign.DropRateMul{})); got[149] != 9 || got[25] != 0 {
		t.Fatalf("medals %v, want the final 9 of medal 149", got)
	}
}

func TestAnEarlierRunsBonusPaysItsMedal(t *testing.T) {
	h := eventRunHandler(t, runLink)
	u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	u.Costumes["c"] = store.CostumeState{UserCostumeUuid: "c", CostumeId: 21001, LimitBreakCount: 1}
	u.Weapons["w"] = store.WeaponState{UserWeaponUuid: "w", WeaponId: 300, LimitBreakCount: 3}
	u.DeckCharacters["d"] = store.DeckCharacterState{UserDeckCharacterUuid: "d", UserCostumeUuid: "c", MainUserWeaponUuid: "w"}
	deck := store.DeckState{UserDeckCharacterUuid01: "d"}
	u.EventQuest.CurrentEventQuestChapterId, u.EventQuest.CurrentQuestId = runChapter, runQuest
	got := medals(h.questBonusDrops(u, h.QuestById[runQuest], deck, 1))
	// character 1001 +2, costume (limit break 1) +3, weapon: the best rule its limit break 3 reaches (2: +5)
	if got[25] != 10 {
		t.Fatalf("bonus medals %v, want 10 of medal 25", got)
	}
}

func TestABonusOutsideAnEarlierRunIsTheGameDatas(t *testing.T) {
	h := eventRunHandler(t, runLink)
	u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	u.EventQuest.CurrentEventQuestChapterId, u.EventQuest.CurrentQuestId = runChapter, 999 // another quest in play
	if got := h.questBonusDrops(u, h.QuestById[runQuest], store.DeckState{}, 1); len(got) != 0 {
		t.Fatalf("bonus %v without a run and without m_quest_bonus", got)
	}
}
