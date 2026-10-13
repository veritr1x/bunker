package questflow

import (
	"testing"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func TestQuestBonusDropsFollowDeckAndLimitBreak(t *testing.T) {
	h := testHandler()
	h.QuestBonus = &masterdata.QuestBonusCatalog{
		BonusById: map[int32]masterdata.EntityMQuestBonus{9: {QuestBonusId: 9, QuestBonusWeaponGroupId: 300, QuestBonusCharacterGroupId: 301}},
		WeaponGroups: map[int32][]masterdata.EntityMQuestBonusWeaponGroup{300: {
			{WeaponId: testWeapon, LimitBreakCountLowerLimit: 0, QuestBonusEffectGroupId: 1027},
			{WeaponId: testWeapon, LimitBreakCountLowerLimit: 1, QuestBonusEffectGroupId: 1028},
			{WeaponId: testWeapon, LimitBreakCountLowerLimit: 2, QuestBonusEffectGroupId: 1029, QuestBonusTermGroupId: 5},
		}},
		CharacterGroups: map[int32][]masterdata.EntityMQuestBonusCharacterGroup{301: {{CharacterId: 1001, QuestBonusEffectGroupId: 1031}}},
		EffectGroups: map[int32][]masterdata.EntityMQuestBonusEffectGroup{
			1027: {{QuestBonusType: masterdata.QuestBonusTypeDropReward, QuestBonusEffectId: 26}},
			1028: {{QuestBonusType: masterdata.QuestBonusTypeDropReward, QuestBonusEffectId: 27}},
			1029: {{QuestBonusType: masterdata.QuestBonusTypeDropReward, QuestBonusEffectId: 28}},
			1031: {{QuestBonusType: masterdata.QuestBonusTypeExp, QuestBonusEffectId: 26}}, // EXP shares effect ids: no drop
		},
		DropRewardsByEffect: map[int32][]masterdata.EntityMQuestBonusDropReward{
			26: {{PossessionType: 6, PossessionId: 1007, AdditionalCount: 2}},
			27: {{PossessionType: 6, PossessionId: 1007, AdditionalCount: 3}},
			28: {{PossessionType: 6, PossessionId: 1007, AdditionalCount: 4}},
		},
		TermsByGroup: map[int32][]masterdata.EntityMQuestBonusTermGroup{5: {{StartDatetime: 100, EndDatetime: 200}}},
	}
	u := testUser()
	w := u.Weapons["w1"]
	w.LimitBreakCount = 2
	u.Weapons["w1"] = w
	deck := u.Decks[store.DeckKey{DeckType: model.DeckTypeQuest, UserDeckNumber: 1}]
	quest := masterdata.EntityMQuest{QuestId: testQuest, QuestBonusId: 9}

	// The LB2 row is out of term at time 0, so the LB1 row (+3) applies.
	got := h.questBonusDrops(u, quest, deck, 0)
	if len(got) != 1 || got[0].Count != 3 {
		t.Fatalf("drops out of term %+v", got)
	}
	got = h.questBonusDrops(u, quest, deck, 150)
	if len(got) != 1 || got[0].Count != 4 {
		t.Fatalf("drops in term %+v", got)
	}
}

func TestImportantItemDropCounts(t *testing.T) {
	h := testHandler()
	h.ImportantItemEffects = &masterdata.ImportantItemEffectCatalog{
		DropCounts: []masterdata.ImportantItemDropCount{{ImportantItemId: 200001, EndDatetime: 1000, CountPermil: 500, QuestGroupId: 101, ItemGroupId: 101}},
		QuestGroups: map[int32][]masterdata.EntityMImportantItemEffectTargetQuestGroup{101: {
			{ImportantItemEffectTargetQuestGroupType: masterdata.ImportantItemTargetMainQuestChapterId, TargetValue: 2},
		}},
		ItemGroups: map[int32][]masterdata.EntityMImportantItemEffectTargetItemGroup{101: {{PossessionType: 6, PossessionId: 1008}}},
	}
	u := testUser()
	main := campaign.QuestTarget{QuestId: testQuest, QuestType: campaign.QuestTypeMainQuest, ChapterId: 2}
	drops := func() []RewardGrant {
		return []RewardGrant{{PossessionType: 6, PossessionId: 1008, Count: 4}, {PossessionType: 6, PossessionId: 1, Count: 4}}
	}
	never := func(int64) int64 { return 999 }

	if got := h.applyImportantItemDropCounts(u, drops(), main, 0, never); got[0].Count != 4 {
		t.Fatal("bonus without owning the item")
	}
	u.ImportantItems[200001] = 1
	got := h.applyImportantItemDropCounts(u, drops(), main, 0, never)
	if got[0].Count != 6 || got[1].Count != 4 {
		t.Fatalf("owned: %+v", got)
	}
	other := main
	other.ChapterId = 3
	if got := h.applyImportantItemDropCounts(u, drops(), other, 0, never); got[0].Count != 4 {
		t.Fatal("bonus outside the target chapters")
	}
	one := []RewardGrant{{PossessionType: 6, PossessionId: 1008, Count: 1}}
	if got := h.applyImportantItemDropCounts(u, one, main, 0, func(int64) int64 { return 0 }); got[0].Count != 2 {
		t.Fatalf("fraction not paid as a chance: %+v", got)
	}
}

func TestLimitContentLocks(t *testing.T) {
	h := testHandler()
	h.QuestById[130001] = masterdata.EntityMQuest{QuestId: 130001}
	h.QuestById[130002] = masterdata.EntityMQuest{QuestId: 130002}
	h.LimitContent = masterdata.BuildLimitContentCatalog(
		[]masterdata.EntityMEventQuestChapterLimitContentRelation{{EventQuestChapterId: 500001, EventQuestLimitContentId: 1}},
		[]masterdata.EntityMEventQuestLimitContent{{EventQuestLimitContentId: 1, EventQuestLimitContentDeckRestrictionId: 2}},
		[]masterdata.EntityMEventQuestLimitContentDeckRestriction{{EventQuestLimitContentDeckRestrictionId: 2, EventQuestLimitContentDeckRestrictionTargetId: 2, EndDatetime: 1000}},
		[]masterdata.EntityMEventQuestLimitContentDeckRestrictionTarget{{EventQuestLimitContentDeckRestrictionTargetId: 2, LimitContentDeckRestrictionType: masterdata.LimitContentDeckRestrictionCostume}},
		[]masterdata.EntityMEventQuestChapter{{EventQuestChapterId: 500001, EventQuestSequenceGroupId: 500001}},
		[]masterdata.EntityMEventQuestSequenceGroup{{EventQuestSequenceGroupId: 500001, DifficultyType: 1, EventQuestSequenceId: 500001}},
		[]masterdata.EntityMEventQuestSequence{{EventQuestSequenceId: 500001, SortOrder: 1, QuestId: 130001}, {EventQuestSequenceId: 500001, SortOrder: 2, QuestId: 130002}},
	)
	u := testUser()

	h.HandleEventQuestStart(u, 500001, 130001, false, 1, 0)
	h.HandleEventQuestFinish(u, 500001, 130001, false, false, 0)
	rows := u.Ext.Quest.LimitContentRestricted
	if len(rows) != 1 || rows[0].TargetUuid != "c1" || rows[0].QuestId != 130001 || rows[0].PossessionType != int32(model.PossessionTypeCostume) {
		t.Fatalf("locks %+v", rows)
	}
	if err := h.CheckLimitContentDeck(u, 500001, 130002, 1, 0); err == nil {
		t.Fatal("deck reusing a locked costume accepted")
	}
	if err := h.CheckLimitContentDeck(u, 500001, 130001, 1, 0); err != nil {
		t.Fatalf("same quest refused: %v", err)
	}

	// Winning the run's last quest ends the run and frees the locks.
	h.HandleEventQuestStart(u, 500001, 130002, false, 1, 0)
	h.HandleEventQuestFinish(u, 500001, 130002, false, false, 0)
	if len(u.Ext.Quest.LimitContentRestricted) != 0 {
		t.Fatalf("locks after the last quest %+v", u.Ext.Quest.LimitContentRestricted)
	}

	h.HandleEventQuestStart(u, 500001, 130001, false, 1, 0)
	h.HandleEventQuestFinish(u, 500001, 130001, false, false, 0)
	u.QuestLimitContentStatus[130001] = store.QuestLimitContentStatus{LimitContentQuestStatusType: 1}
	h.ResetLimitContentRun(u, 500001, h.LimitContentRunQuests(500001, 130002))
	if len(u.Ext.Quest.LimitContentRestricted) != 0 || len(u.QuestLimitContentStatus) != 0 {
		t.Fatal("reset kept the run")
	}
}
