package questflow

import (
	"testing"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

func testCollection() []masterdata.CollectionBonus {
	return []masterdata.CollectionBonus{
		{Id: 201, GroupingId: 5, EffectType: masterdata.CollectionBonusCostumeExp, Costumes: []int32{11, 22},
			Amounts: [5]int32{60, 70, 80, 90, 100}, MainChapters: map[int32]bool{2: true, 3: true}, EndDatetime: 1000},
		{Id: 301, GroupingId: 8, EffectType: masterdata.CollectionBonusGold, Costumes: []int32{11, 22},
			Amounts: [5]int32{10, 20, 30, 40, 50}, MainChapters: map[int32]bool{2: true}, EndDatetime: 1000},
		{Id: 302, GroupingId: 8, EffectType: masterdata.CollectionBonusGold, Costumes: []int32{33},
			Amounts: [5]int32{15, 30, 45, 60, 75}, MainChapters: map[int32]bool{2: true}, EndDatetime: 1000},
		{Id: 401, GroupingId: 9, EffectType: masterdata.CollectionBonusGold, Costumes: []int32{33},
			Amounts: [5]int32{100, 200, 300, 400, 500}, MainChapters: map[int32]bool{2: true}, EndDatetime: 1000},
	}
}

func ownCostume(u *store.UserState, uuid string, id, limitBreak int32) {
	u.Costumes[uuid] = store.CostumeState{UserCostumeUuid: uuid, CostumeId: id, LimitBreakCount: limitBreak}
}

func TestCollectionPermilLevelIsTheLowestLimitBreak(t *testing.T) {
	u := testUser()
	ownCostume(u, "a", 11, 0)
	ownCostume(u, "b", 22, 4)
	if got := collectionPermil(testCollection(), u, 2, masterdata.CollectionBonusCostumeExp, 0); got != 600 {
		t.Fatalf("LB 0 and 4: %d, want 60%% = 600‰", got)
	}
	ownCostume(u, "a", 11, 3)
	if got := collectionPermil(testCollection(), u, 2, masterdata.CollectionBonusCostumeExp, 0); got != 900 {
		t.Fatalf("LB 3 and 4: %d, want 900", got)
	}
	ownCostume(u, "c", 11, 4) // a second copy at a higher limit break: the best owned copy counts
	if got := collectionPermil(testCollection(), u, 2, masterdata.CollectionBonusCostumeExp, 0); got != 1000 {
		t.Fatalf("best copies LB 4 and 4: %d, want 1000", got)
	}
}

func TestCollectionPermilNeedsTheWholeSet(t *testing.T) {
	u := testUser()
	ownCostume(u, "a", 11, 4)
	if got := collectionPermil(testCollection(), u, 2, masterdata.CollectionBonusCostumeExp, 0); got != 0 {
		t.Fatalf("one costume missing: %d", got)
	}
}

func TestCollectionPermilOnlyOnItsChaptersAndDates(t *testing.T) {
	u := testUser()
	ownCostume(u, "a", 11, 0)
	ownCostume(u, "b", 22, 0)
	for _, c := range []int32{0, 4} {
		if got := collectionPermil(testCollection(), u, c, masterdata.CollectionBonusCostumeExp, 0); got != 0 {
			t.Fatalf("chapter %d: %d", c, got)
		}
	}
	if got := collectionPermil(testCollection(), u, 2, masterdata.CollectionBonusCostumeExp, 2000); got != 0 {
		t.Fatalf("after the bonus ended: %d", got)
	}
}

func TestCollectionPermilGroupingTakesTheLargest(t *testing.T) {
	u := testUser()
	ownCostume(u, "a", 11, 1)
	ownCostume(u, "b", 22, 1)
	ownCostume(u, "c", 33, 1)
	// Grouping 8: 20% (301) and 30% (302) → 30%; grouping 9: 200%.
	if got := collectionPermil(testCollection(), u, 2, masterdata.CollectionBonusGold, 0); got != 2300 {
		t.Fatalf("gold: %d, want 300 + 2000", got)
	}
}

func TestDropBoostAddsTheCollectionDropRateOnMainQuests(t *testing.T) {
	saved := collectionBonusCatalog
	t.Cleanup(func() { collectionBonusCatalog = saved })
	collectionBonusCatalog = func() []masterdata.CollectionBonus {
		return []masterdata.CollectionBonus{{Id: 402, GroupingId: 12, EffectType: masterdata.CollectionBonusDropRate, Costumes: []int32{11},
			Amounts: [5]int32{100, 200, 300, 400, 500}, MainChapters: map[int32]bool{2: true}, EndDatetime: 1000}}
	}
	h := testHandler()
	u := testUser()
	ownCostume(u, "a", 11, 0)
	main := campaign.QuestTarget{QuestId: testQuest, QuestType: campaign.QuestTypeMainQuest, ChapterId: 2}
	if b := h.dropBoostFor(u, main, 0); b == nil || b(tMaterial, 7) != 1000 {
		t.Fatal("main chapter 2 should get +100% on every drop")
	}
	event := campaign.QuestTarget{QuestId: testQuest, QuestType: campaign.QuestTypeEventQuest, ChapterId: 2}
	if b := h.dropBoostFor(u, event, 0); b != nil && b(tMaterial, 7) != 0 {
		t.Fatal("an event chapter with the same id gets no collection bonus")
	}
}

func TestMainQuestGoldGetsTheCollectionBonus(t *testing.T) {
	saved := collectionBonusCatalog
	t.Cleanup(func() { collectionBonusCatalog = saved })
	collectionBonusCatalog = testCollection
	onChapter2(t)
	h := testHandler()
	q := h.QuestById[testQuest]
	q.QuestId, q.Gold, q.UserExp, q.CharacterExp, q.CostumeExp = testQuest, 100, 0, 0, 0
	h.QuestById[testQuest] = q
	gold := h.Config.ConsumableItemIdForGold
	u := testUser()
	ownCostume(u, "a", 11, 0)
	ownCostume(u, "b", 22, 0)
	before := u.ConsumableItems[gold]
	h.applyExpAndGoldRewards(u, testQuest, 0)
	if got := u.ConsumableItems[gold] - before; got != 110 {
		t.Fatalf("gold +%d, want 100 +10%%", got)
	}
}

// onChapter2 puts testQuest in main chapter 2 the way every difficulty and
// replay is looked up (the handler's own map holds Normal quests only).
func onChapter2(t *testing.T) {
	saved := mainQuestChapterOf
	t.Cleanup(func() { mainQuestChapterOf = saved })
	mainQuestChapterOf = func(questId int32) int32 {
		if questId == testQuest {
			return 2
		}
		return 0
	}
}

func TestQuestSkipGoldGetsTheCollectionBonus(t *testing.T) {
	saved := collectionBonusCatalog
	t.Cleanup(func() { collectionBonusCatalog = saved })
	collectionBonusCatalog = testCollection
	onChapter2(t)
	h := testHandler()
	h.QuestById[testQuest] = masterdata.EntityMQuest{QuestId: testQuest, Stamina: 1, Gold: 100}
	h.MaxStaminaByLevel = map[int32]int32{1: 50}
	u := testUser()
	u.Status.Level = 1
	u.Status.StaminaMilliValue = 50000
	u.ConsumableItems[h.Config.ConsumableItemIdForQuestSkipTicket] = 5
	ownCostume(u, "a", 11, 0)
	ownCostume(u, "b", 22, 0)
	gold := h.Config.ConsumableItemIdForGold
	before := u.ConsumableItems[gold]
	if _, err := h.HandleQuestSkip(u, testQuest, 2, 1, 0); err != nil {
		t.Fatal(err)
	}
	if got := u.ConsumableItems[gold] - before; got != 220 {
		t.Fatalf("2 skips: gold +%d, want 2 × 110", got)
	}
}

func TestDropBoostFindsTheChapterOfAnyDifficulty(t *testing.T) {
	saved := collectionBonusCatalog
	t.Cleanup(func() { collectionBonusCatalog = saved })
	collectionBonusCatalog = func() []masterdata.CollectionBonus {
		return []masterdata.CollectionBonus{{Id: 402, GroupingId: 12, EffectType: masterdata.CollectionBonusDropRate, Costumes: []int32{11},
			Amounts: [5]int32{100, 200, 300, 400, 500}, MainChapters: map[int32]bool{2: true}, EndDatetime: 1000}}
	}
	onChapter2(t)
	h := testHandler()
	u := testUser()
	ownCostume(u, "a", 11, 0)
	hard := campaign.QuestTarget{QuestId: testQuest, QuestType: campaign.QuestTypeMainQuest} // no ChapterId: a Hard quest
	if b := h.dropBoostFor(u, hard, 0); b == nil || b(tMaterial, 7) != 1000 {
		t.Fatal("a Hard quest of chapter 2 gets the bonus")
	}
}
