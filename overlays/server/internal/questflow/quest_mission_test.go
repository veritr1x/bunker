package questflow

import (
	"errors"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

const (
	testQuest   = 7001
	testCostume = 21001 // character 1001, skillful weapon 1
	testWeapon  = 500   // attribute 2
)

func testHandler(missions ...masterdata.EntityMQuestMission) *QuestHandler {
	cat := &masterdata.QuestCatalog{
		QuestById:                 map[int32]masterdata.EntityMQuest{testQuest: {QuestId: testQuest}},
		MissionById:               map[int32]masterdata.EntityMQuestMission{},
		MissionIdsByQuestId:       map[int32][]int32{},
		MissionRewardsByMissionId: map[int32][]masterdata.EntityMQuestMissionReward{},
		MissionConditionValues:    map[int32][]int32{10101: {1001, 1002}},
		CostumeById: map[int32]masterdata.EntityMCostume{
			testCostume: {CostumeId: testCostume, CharacterId: 1001, SkillfulWeaponType: 1, RarityType: 30},
		},
		WeaponById: map[int32]masterdata.EntityMWeapon{testWeapon: {WeaponId: testWeapon, AttributeType: 2, RarityType: 30}},
	}
	for _, m := range missions {
		cat.MissionById[m.QuestMissionId] = m
		cat.MissionIdsByQuestId[testQuest] = append(cat.MissionIdsByQuestId[testQuest], m.QuestMissionId)
		cat.MissionRewardsByMissionId[m.QuestMissionRewardId] = []masterdata.EntityMQuestMissionReward{
			{QuestMissionRewardId: m.QuestMissionRewardId, PossessionType: int32(model.PossessionTypeConsumableItem), PossessionId: m.QuestMissionId, Count: 1},
		}
	}
	return &QuestHandler{QuestCatalog: cat, Config: &masterdata.GameConfig{QuestSkipMaxCountAtOnce: 100, ConsumableItemIdForQuestSkipTicket: 2003}, Granter: &store.PossessionGranter{}}
}

// testUser has one quest deck (number 1) with testCostume and testWeapon.
func testUser() *store.UserState {
	u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	u.Costumes["c1"] = store.CostumeState{UserCostumeUuid: "c1", CostumeId: testCostume}
	u.Weapons["w1"] = store.WeaponState{UserWeaponUuid: "w1", WeaponId: testWeapon}
	u.DeckCharacters["d1"] = store.DeckCharacterState{UserDeckCharacterUuid: "d1", UserCostumeUuid: "c1", MainUserWeaponUuid: "w1"}
	u.Decks[store.DeckKey{DeckType: model.DeckTypeQuest, UserDeckNumber: 1}] = store.DeckState{
		DeckType: model.DeckTypeQuest, UserDeckNumber: 1, UserDeckCharacterUuid01: "d1", Power: 5000,
	}
	return u
}

func mission(id, condType, value int32) masterdata.EntityMQuestMission {
	return masterdata.EntityMQuestMission{QuestMissionId: id, QuestMissionConditionType: condType, ConditionValue: value, QuestMissionRewardId: id}
}

func TestRecordFinishWaveSumsAndMaxes(t *testing.T) {
	u := testUser()
	RecordStartWave(u, []*pb.UserPartyInitialInfo{{DeckType: int32(model.DeckTypeQuest), UserDeckNumber: 1}})
	RecordFinishWave(u, &pb.BattleDetail{CharacterDeathCount: 1, MaxDamage: 900, CriticalCount: 3, ComboCount: 10, PlayerWeaponActiveSkillUsedCount: 2,
		CostumeBattleInfo: []*pb.CostumeBattleInfo{{MaxHp: 100, RemainingHp: 10}}})
	RecordFinishWave(u, &pb.BattleDetail{MaxDamage: 400, CriticalCount: 2, ComboCount: 25, PlayerWeaponActiveSkillUsedCount: 1, TotalRecoverPoint: 5,
		CostumeBattleInfo: []*pb.CostumeBattleInfo{{MaxHp: 100, RemainingHp: 90}}})
	b := u.Ext.Quest.Battle
	if b.Waves != 2 || b.CharacterDeathCount != 1 || b.MaxDamage != 900 || b.CriticalCount != 5 || b.MaxComboCount != 25 ||
		b.WeaponSkillUseCount != 3 || b.TotalRecoverPoint != 5 || b.DeckNumber != 1 {
		t.Fatalf("battle record %+v", b)
	}
	if len(b.LastWaveHp) != 1 || b.LastWaveHp[0].RemainingHp != 90 {
		t.Fatalf("last wave hp %+v", b.LastWaveHp)
	}
	ResetBattleStats(u)
	if u.Ext.Quest.Battle.Waves != 0 {
		t.Fatal("reset kept the record")
	}
}

func TestMissionConditions(t *testing.T) {
	h := testHandler()
	u := testUser()
	deck := h.missionDeckFor(u, testQuest) // no quest deck number yet: empty
	if len(deck.units) != 0 {
		t.Fatal("deck resolved without a deck number")
	}
	RecordStartWave(u, []*pb.UserPartyInitialInfo{{DeckType: int32(model.DeckTypeQuest), UserDeckNumber: 1}})
	deck = h.missionDeckFor(u, testQuest)
	b := store.QuestBattleState{CharacterDeathCount: 1, MaxDamage: 800, WeaponSkillUseCount: 3, CriticalCount: 5, MaxComboCount: 20,
		LastWaveHp: []store.BattleHpState{{MaxHp: 1000, RemainingHp: 800}}}
	cases := []struct {
		m    masterdata.EntityMQuestMission
		want bool
	}{
		{mission(1, 1, 1), true},   // at most 1 down
		{mission(2, 1, 0), false},  // nobody down
		{mission(3, 2, 700), true}, // max damage
		{mission(4, 2, 1500), false},
		{mission(5, 4, 1001), true}, // character in deck
		{mission(6, 4, 1002), false},
		{mission(7, 5, 2), true}, // main weapon attribute in deck
		{mission(8, 7, 3), true}, // weapon skills >= 3
		{mission(9, 10, 1), true},
		{mission(10, 19, 2), true}, // every main weapon attribute 2
		{mission(11, 49, 1), true}, // deck of <= 1 costume
		{mission(12, 50, 6), false},
		{mission(13, 51, 80), true},
		{mission(14, 51, 81), false},
		{mission(15, 52, 20), true},
		{mission(16, 55, 0), false}, // no weapon skills
		{mission(17, 57, 0), true},  // no recovery
		{masterdata.EntityMQuestMission{QuestMissionId: 18, QuestMissionConditionType: 61, QuestMissionConditionValueGroupId: 10101}, false},
		{masterdata.EntityMQuestMission{QuestMissionId: 19, QuestMissionConditionType: 65, QuestMissionConditionValueGroupId: 10101}, false},
		{mission(20, 41, 1), true}, // PARTS_GROUP_ID: not judged, clears on a win
	}
	for _, c := range cases {
		if got := h.missionConditionMet(c.m, deck, b); got != c.want {
			t.Errorf("mission %d (type %d, value %d): got %v, want %v", c.m.QuestMissionId, c.m.QuestMissionConditionType, c.m.ConditionValue, got, c.want)
		}
	}
}

func TestQuestMissionsClearOnlyOnWinAndPayOnce(t *testing.T) {
	h := testHandler(mission(1, 2, 1000), mission(2, 4, 1001), mission(3, 9999, 0))
	u := testUser()
	h.HandleExtraQuestStart(u, testQuest, 1, 0)
	RecordFinishWave(u, &pb.BattleDetail{MaxDamage: 500})

	out := h.HandleExtraQuestFinish(u, testQuest, true, false, 0)
	if len(out.MissionClearRewards) != 0 || u.QuestMissions[store.QuestMissionKey{QuestId: testQuest, QuestMissionId: 2}].IsClear {
		t.Fatal("a retire cleared missions")
	}
	if st := u.Quests[testQuest].QuestStateType; st != model.UserQuestStateTypeChallenged {
		t.Fatalf("state after a first retire %d, want challenged", st)
	}

	h.HandleExtraQuestStart(u, testQuest, 1, 0)
	RecordFinishWave(u, &pb.BattleDetail{MaxDamage: 500})
	out = h.HandleExtraQuestFinish(u, testQuest, false, false, 0)
	if len(out.MissionClearRewards) != 1 || out.MissionClearRewards[0].PossessionId != 2 || out.IsBigWin {
		t.Fatalf("first win rewards %+v bigwin %v", out.MissionClearRewards, out.IsBigWin)
	}

	// A later win that meets the damage mission pays it and the complete reward.
	h.HandleExtraQuestStart(u, testQuest, 1, 0)
	RecordFinishWave(u, &pb.BattleDetail{MaxDamage: 1200})
	out = h.HandleExtraQuestFinish(u, testQuest, false, false, 0)
	if len(out.MissionClearRewards) != 1 || out.MissionClearRewards[0].PossessionId != 1 {
		t.Fatalf("replay rewards %+v", out.MissionClearRewards)
	}
	if !out.IsBigWin || len(out.MissionClearCompleteRewards) != 1 || out.BigWinClearedQuestMissionIds[0] != 3 {
		t.Fatalf("complete reward %+v bigwin %v", out.MissionClearCompleteRewards, out.IsBigWin)
	}

	// Nothing left to pay; a loss now keeps the quest cleared.
	h.HandleExtraQuestStart(u, testQuest, 1, 0)
	RecordFinishWave(u, &pb.BattleDetail{MaxDamage: 1200})
	out = h.HandleExtraQuestFinish(u, testQuest, false, false, 0)
	if len(out.MissionClearRewards)+len(out.MissionClearCompleteRewards) != 0 {
		t.Fatal("missions paid twice")
	}
	h.HandleExtraQuestStart(u, testQuest, 1, 0)
	h.HandleExtraQuestFinish(u, testQuest, false, true, 0)
	if st := u.Quests[testQuest].QuestStateType; st != model.UserQuestStateTypeCleared {
		t.Fatalf("state after a wipe of a cleared quest %d", st)
	}
}

func TestQuestSkipGuards(t *testing.T) {
	h := testHandler()
	h.QuestById[testQuest] = masterdata.EntityMQuest{QuestId: testQuest, Stamina: 10}
	h.MaxStaminaByLevel = map[int32]int32{1: 50}
	u := testUser()
	u.Status.Level = 1
	u.Status.StaminaMilliValue = 25000
	u.ConsumableItems[2003] = 5

	for _, n := range []int32{0, 101, 3, 6} { // bad counts, too little stamina (30 > 25), too few tickets
		if _, err := h.HandleQuestSkip(u, testQuest, n, 1, 0); !errors.Is(err, ErrSkipRefused) {
			t.Fatalf("skip %d: err %v", n, err)
		}
	}
	if u.ConsumableItems[2003] != 5 || u.Status.StaminaMilliValue != 25000 {
		t.Fatal("a refused skip changed the save")
	}
	if _, err := h.HandleQuestSkip(u, testQuest, 2, 1, 0); err != nil {
		t.Fatal(err)
	}
	if u.ConsumableItems[2003] != 3 || u.Status.StaminaMilliValue != 5000 || u.Quests[testQuest].ClearCount != 2 {
		t.Fatalf("after skip: tickets %d stamina %d clears %d", u.ConsumableItems[2003], u.Status.StaminaMilliValue, u.Quests[testQuest].ClearCount)
	}
}
