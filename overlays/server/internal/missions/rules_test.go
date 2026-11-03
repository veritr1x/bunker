package missions

import (
	"encoding/json"
	"os"
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/masterdata/memorydb"
	"lunar-tear/server/internal/store"
)

func missionDefinition(id int32, signature ruleCondition, target int32) masterdata.EntityMMission {
	return masterdata.EntityMMission{MissionId: id, MissionClearConditionType: signature[0],
		MissionClearConditionGroupId: signature[1], MissionClearConditionOptionGroupId: signature[2],
		MissionClearConditionOptionDetailGroupId: signature[3], ClearConditionValue: target}
}

func TestRegionalRuleSelection(t *testing.T) {
	s, err := loadRules()
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		id              int32
		condition       ruleCondition
		kind            string
		costume, weapon int32
	}{
		{1166, ruleCondition{43, 200, 200, 0}, "weapon_level", 0, 250011},       // Global
		{1166, ruleCondition{11, 199, 199, 0}, "costume_limit_break", 25002, 0}, // JP
		{1162, ruleCondition{40, 197, 197, 0}, "costume_level", 25002, 0},
		{1163, ruleCondition{10, 198, 198, 0}, "costume_skill", 25002, 0},
		{1170, ruleCondition{43, 200, 200, 0}, "weapon_level", 0, 250011},
		{1174, ruleCondition{6, 201, 201, 0}, "weapon_skill", 0, 250011},
		{1176, ruleCondition{8, 202, 202, 0}, "weapon_limit_break", 0, 250011},
		{3, ruleCondition{26, 3, 0, 0}, "explore_finish", 0, 0},
		{20401, ruleCondition{65, 20401, 0, 0}, "stamina", 0, 0},
		{1010509, ruleCondition{1, 1010509, 101030801, 0}, "quest", 0, 0},
	} {
		r, ok := s.find(missionDefinition(tc.id, tc.condition, 80))
		if !ok || r.MissionId != tc.id || r.Kind != tc.kind ||
			(tc.costume != 0 && !contains(r.Costumes, tc.costume)) || (tc.weapon != 0 && !contains(r.Weapons, tc.weapon)) {
			t.Errorf("mission %d, %v: %+v, found %v", tc.id, tc.condition, r, ok)
		}
	}
	// JP's unfiltered exploration mission must accept both games; Global's
	// same ID only counts Shooting. Neither may inherit the other's filter.
	jp, _ := s.find(missionDefinition(3, ruleCondition{26, 3, 0, 0}, 1))
	gl, _ := s.find(missionDefinition(3, ruleCondition{26, 3, 3, 0}, 1))
	if len(jp.Explores) != 0 || len(gl.Explores) != 1 || gl.Explores[0] != 1 {
		t.Fatalf("exploration filters: JP %+v, Global %+v", jp, gl)
	}
	pass, _ := s.find(missionDefinition(1010509, ruleCondition{1, 1010509, 101030801, 0}, 10))
	if pass.Quest == nil || len(pass.Quest.EventTypes) != 1 || pass.Quest.EventTypes[0] != 3 {
		t.Fatalf("JP pass filter: %+v", pass)
	}
	if _, ok := s.find(missionDefinition(7011, ruleCondition{56, 7011, 394, 0}, 1)); ok {
		t.Fatal("unverified JP profile phrase inherited a Global rule")
	}
	if _, ok := s.find(missionDefinition(1166, ruleCondition{11, 199, 99999, 0}, 2)); ok {
		t.Fatal("unknown filter inherited a rule by ID")
	}
	if _, ok := s.find(missionDefinition(99999999, ruleCondition{11, 199, 199, 0}, 2)); ok {
		t.Fatal("an unverified mission inherited a rule from a shared counter")
	}
	// Binding must preserve every existing Global rule, including signatures
	// shared by differently named quests with different filters.
	var base []Rule
	if err := json.Unmarshal(rulesJSON, &base); err != nil {
		t.Fatal(err)
	}
	for _, want := range base {
		got, ok := s.find(missionDefinition(want.MissionId, want.Condition, 1))
		if !ok || ruleRevision(got) != ruleRevision(want) {
			t.Fatalf("Global rule %d changed", want.MissionId)
		}
	}
}

func TestAmbiguousCounterDoesNotGuessFilter(t *testing.T) {
	sig := ruleCondition{1, 7, 8, 0}
	s, err := newRuleSet([]Rule{{MissionId: 1, Condition: sig, Kind: "quest", Quest: &QuestFilter{Main: true}},
		{MissionId: 2, Condition: sig, Kind: "quest", Quest: &QuestFilter{Event: true}}}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := s.find(missionDefinition(3, sig, 1)); ok {
		t.Fatal("ambiguous filter assigned to a different ID")
	}
	if _, ok := s.find(missionDefinition(1, sig, 1)); !ok {
		t.Fatal("exact definition should still resolve")
	}
}

func regionalTestCatalog(t *testing.T) (*Catalog, *Mission) {
	t.Helper()
	s, err := loadRules()
	if err != nil {
		t.Fatal(err)
	}
	row := missionDefinition(1166, ruleCondition{11, 199, 199, 0}, 2)
	r, ok := s.find(row)
	if !ok {
		t.Fatal("JP costume mission missing")
	}
	m := &Mission{EntityMMission: row, Rule: r, Category: 3}
	return &Catalog{Missions: []*Mission{m}, ById: map[int32]*Mission{1166: m},
		ByKind: map[string][]*Mission{r.Kind: {m}}, ruleChanges: map[int32]string{1166: s.change(1166, r)},
		Rewards: map[int32][]masterdata.EntityMMissionReward{}}, m
}

func TestJapaneseCostumeMissionRejectsWeaponLevel(t *testing.T) {
	cat, m := regionalTestCatalog(t)
	u := store.UserState{UserId: 1}
	u.EnsureMaps()
	u.Ext.MissionsVersion = trackVersion
	u.Weapons["weapon"] = store.WeaponState{WeaponId: 250011, Level: 30}
	u.Costumes["costume"] = store.CostumeState{CostumeId: 25002, Level: 1}
	before := store.CloneUserState(u)
	cat.Track(&before, &u, "/apb.api.user.UserService/GameStart", nil, 1000)
	if u.Missions[m.MissionId].MissionProgressStatusType >= StatusClear {
		t.Fatal("weapon level completed costume limit breaks")
	}
	before = store.CloneUserState(u)
	co := u.Costumes["costume"]
	co.LimitBreakCount = 2
	u.Costumes["costume"] = co
	cat.Track(&before, &u, "/apb.api.costume.CostumeService/LimitBreak", nil, 2000)
	if got := u.Missions[m.MissionId]; got.MissionProgressStatusType != StatusClear || got.ProgressValue != 2 {
		t.Fatalf("correct costume ascension did not complete: %+v", got)
	}
}

func TestRegionalRepairBeforeClaimAndAcrossMasterSwitch(t *testing.T) {
	cat, m := regionalTestCatalog(t)
	m.MissionRewardId = 1
	cat.Rewards[1] = []masterdata.EntityMMissionReward{{PossessionType: 6, PossessionId: 1, Count: 1000}}
	u := store.UserState{UserId: 1}
	u.EnsureMaps()
	u.Missions[1166] = store.UserMissionState{MissionId: 1166, ProgressValue: 2, MissionProgressStatusType: StatusClear, ClearDatetime: 1}
	g := &store.PossessionGranter{}
	if got := cat.ReceiveMissions(&u, g, []int32{1166}, 1000); len(got) != 0 || u.ConsumableItems[1] != 0 {
		t.Fatal("stale completion paid before tracking could repair it")
	}
	if rec := u.Missions[1166]; rec.ProgressValue != 0 || rec.ClearDatetime != 0 || rec.MissionProgressStatusType != StatusInProgress {
		t.Fatalf("stale progress not cleared: %+v", rec)
	}
	// Later valid progress survives the next request and still pays once.
	u.Missions[1166] = store.UserMissionState{MissionId: 1166, ProgressValue: 2, MissionProgressStatusType: StatusClear}
	if got := cat.ReceiveMissions(&u, g, []int32{1166, 1166}, 2000); len(got) != 1 || u.ConsumableItems[1] != 1000 {
		t.Fatalf("valid claim: %+v, coins %d", got, u.ConsumableItems[1])
	}
	u.Ext.MissionRuleRevisions = nil // An already-paid legacy completion must never reopen.
	if got := cat.ReceiveMissions(&u, g, []int32{1166}, 3000); len(got) != 0 || u.Missions[1166].MissionProgressStatusType != StatusRewardReceived {
		t.Fatal("repair reopened a paid reward")
	}
	clone := store.CloneUserState(u)
	clone.Ext.MissionRuleRevisions[1166] = "changed"
	if u.Ext.MissionRuleRevisions[1166] == "changed" || clone.Ext.Equal(u.Ext) {
		t.Fatal("rule revision map is aliased or omitted from equality")
	}
	// Importing Global data also discards unclaimed progress from a JP rule.
	u.Missions[1166] = store.UserMissionState{MissionId: 1166, ProgressValue: 1, MissionProgressStatusType: StatusInProgress}
	global := &Catalog{ById: map[int32]*Mission{1166: {EntityMMission: masterdata.EntityMMission{MissionId: 1166}}}}
	global.reconcileRules(&u, 4000)
	if u.Missions[1166].ProgressValue != 0 || len(u.Ext.MissionRuleRevisions) != 0 {
		t.Fatal("regional progress survived master switch")
	}
}

// Optional private fixtures validate selection against the actual encrypted
// masters. No game data is committed and input files are only read.
func TestRegionalMasterDefinitions(t *testing.T) {
	for _, env := range []string{"BUNKER_TEST_JP_MASTER", "BUNKER_TEST_GLOBAL_MASTER"} {
		t.Run(env, func(t *testing.T) {
			path := os.Getenv(env)
			if path == "" {
				t.Skip("set " + env)
			}
			if err := memorydb.Init(path); err != nil {
				t.Fatal(err)
			}
			cat, err := load()
			if err != nil {
				t.Fatal(err)
			}
			for _, m := range cat.Missions {
				if m.Rule.Kind != "" && m.Rule.Condition != condition(m.EntityMMission) {
					t.Fatalf("mission %d has a rule for another definition", m.MissionId)
				}
			}
			m := cat.ById[1166]
			if env == "BUNKER_TEST_JP_MASTER" {
				if m.Rule.Kind != "costume_limit_break" || !contains(m.Rule.Costumes, 25002) {
					t.Fatalf("JP rule: %+v", m.Rule)
				}
				for id := int32(20401); id <= 20407; id++ {
					if cat.ById[id].Rule.Kind != "stamina" {
						t.Errorf("JP-only stamina mission %d unsupported", id)
					}
				}
			} else {
				if m.Rule.Kind != "weapon_level" || len(cat.ruleChanges) != 0 {
					t.Fatalf("Global rule: %+v, %d unexpected revisions", m.Rule, len(cat.ruleChanges))
				}
			}
		})
	}
}
