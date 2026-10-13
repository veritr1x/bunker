package masterdata

import (
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func TestTierRewardsPaysOnlyHighestTier(t *testing.T) {
	c := &BigHuntCatalog{
		ScoreRewardThresholds: map[int32][]ScoreRewardThreshold{1: {{0, 10}, {2000, 20}, {4000, 30}}},
		RewardItems: map[int32][]RewardItem{
			10: {{PossessionType: 6, PossessionId: 30, Count: 1}},
			20: {{PossessionType: 6, PossessionId: 30, Count: 2}},
			30: {{PossessionType: 6, PossessionId: 30, Count: 3}},
		},
	}
	for score, want := range map[int64]int32{0: 1, 1999: 1, 2000: 2, 99999: 3} {
		got := c.TierRewards(1, score)
		if len(got) != 1 || got[0].Count != want {
			t.Errorf("score %d: %+v, want count %d", score, got, want)
		}
	}
	if got := c.TierRewards(2, 5000); got != nil {
		t.Errorf("unknown group: %+v", got)
	}
}

func TestLimitContentCatalog(t *testing.T) {
	c := BuildLimitContentCatalog(
		[]EntityMEventQuestChapterLimitContentRelation{{EventQuestChapterId: 500001, EventQuestLimitContentId: 1}},
		[]EntityMEventQuestLimitContent{{EventQuestLimitContentId: 1, EventQuestLimitContentDeckRestrictionId: 2}},
		[]EntityMEventQuestLimitContentDeckRestriction{{EventQuestLimitContentDeckRestrictionId: 2, EventQuestLimitContentDeckRestrictionTargetId: 2, StartDatetime: 100, EndDatetime: 200}},
		[]EntityMEventQuestLimitContentDeckRestrictionTarget{{EventQuestLimitContentDeckRestrictionTargetId: 2, LimitContentDeckRestrictionType: LimitContentDeckRestrictionCostume}},
		[]EntityMEventQuestChapter{{EventQuestChapterId: 500001, EventQuestSequenceGroupId: 500001}, {EventQuestChapterId: 9, EventQuestSequenceGroupId: 9}},
		[]EntityMEventQuestSequenceGroup{{EventQuestSequenceGroupId: 500001, DifficultyType: 1, EventQuestSequenceId: 500001}, {EventQuestSequenceGroupId: 9, DifficultyType: 1, EventQuestSequenceId: 9}},
		[]EntityMEventQuestSequence{{EventQuestSequenceId: 500001, SortOrder: 2, QuestId: 130002}, {EventQuestSequenceId: 500001, SortOrder: 1, QuestId: 130001}, {EventQuestSequenceId: 9, SortOrder: 1, QuestId: 9}},
	)
	seq := c.SequenceByQuestId[130002]
	if seq == nil || seq.EventQuestChapterId != 500001 || len(seq.QuestIds) != 2 || seq.QuestIds[0] != 130001 {
		t.Fatalf("sequence %+v", seq)
	}
	if c.SequenceByQuestId[9] != nil {
		t.Fatal("a chapter that is not limit content got a sequence")
	}
	if got := c.RestrictionTypes(500001, 150); len(got) != 1 || got[0] != LimitContentDeckRestrictionCostume {
		t.Fatalf("restriction types %v", got)
	}
	if got := c.RestrictionTypes(500001, 300); len(got) != 0 {
		t.Fatalf("restriction out of term: %v", got)
	}
}

func TestGimmickReleaseCondition(t *testing.T) {
	other := func(gimmickId int64) *gimmickCondition {
		return &gimmickCondition{funcType: evalFuncOtherGimmickBitCount, evalType: evalTypeGe, values: []int64{1001515, 1001515, gimmickId, 1, 1}}
	}
	c := &GimmickCatalog{releaseConditions: map[int32]*gimmickCondition{
		101001001: {funcType: evalFuncRecursion, evalType: evalTypeOr, subs: []*gimmickCondition{other(102015015), other(102015016)}},
	}}
	u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	if c.GimmickReleased(*u, 101001001) {
		t.Fatal("released before any other gimmick was found")
	}
	if !c.GimmickReleased(*u, 5) {
		t.Fatal("a gimmick without a condition is not released")
	}
	u.Gimmick.OrnamentProgress[store.GimmickOrnamentKey{GimmickSequenceScheduleId: 1001515, GimmickSequenceId: 1001515, GimmickId: 102015016, GimmickOrnamentIndex: 1}] =
		store.GimmickOrnamentProgressState{ProgressValueBit: 1}
	if !c.GimmickReleased(*u, 101001001) {
		t.Fatal("not released after one of the OR gimmicks was found")
	}
}
