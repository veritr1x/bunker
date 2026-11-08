package lunarbase

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// The player owns costume 100 (level 50) in Arena deck 1 with weapon w-own;
// the stage holds costume 100 and costume 200 fully raised, weapon w-stage
// and a memoir with a crit-rate main.
func deckWriteStates() (*store.UserState, *store.UserState) {
	u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	u.Costumes["c-own"] = store.CostumeState{UserCostumeUuid: "c-own", CostumeId: 100, Level: 50, LimitBreakCount: 1, AwakenCount: 0}
	u.Characters[10] = store.CharacterState{CharacterId: 10, Level: 1}
	u.Weapons["w-own"] = store.WeaponState{UserWeaponUuid: "w-own", WeaponId: 7, Level: 12}
	u.Costumes["c-other"] = store.CostumeState{UserCostumeUuid: "c-other", CostumeId: 300, Level: 40}
	u.DeckCharacters["dc-1"] = store.DeckCharacterState{UserDeckCharacterUuid: "dc-1", UserCostumeUuid: "c-own", MainUserWeaponUuid: "w-own"}
	u.Decks[store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: 1}] = store.DeckState{DeckType: model.DeckTypePvp, UserDeckNumber: 1, UserDeckCharacterUuid01: "dc-1", Name: "Mine"}
	u.DeckCharacters["dc-q"] = store.DeckCharacterState{UserDeckCharacterUuid: "dc-q", UserCostumeUuid: "c-other"}
	u.Decks[store.DeckKey{DeckType: model.DeckTypeQuest, UserDeckNumber: 1}] = store.DeckState{DeckType: model.DeckTypeQuest, UserDeckNumber: 1, UserDeckCharacterUuid01: "dc-q"}

	s := store.SeedUserState(1, "stage", 0, model.DefaultPlatform)
	s.Costumes["s-100"] = store.CostumeState{UserCostumeUuid: "s-100", CostumeId: 100, Level: 100, LimitBreakCount: 4, AwakenCount: 5, CostumeLotteryEffectUnlockedSlotCount: 3}
	s.CostumeActiveSkills["s-100"] = store.CostumeActiveSkillState{UserCostumeUuid: "s-100", Level: 15}
	s.Costumes["s-200"] = store.CostumeState{UserCostumeUuid: "s-200", CostumeId: 200, Level: 100, LimitBreakCount: 4, AwakenCount: 5}
	s.CostumeActiveSkills["s-200"] = store.CostumeActiveSkillState{UserCostumeUuid: "s-200", Level: 15}
	s.Characters[10] = store.CharacterState{CharacterId: 10, Level: 1}
	s.Characters[20] = store.CharacterState{CharacterId: 20, Level: 1}
	s.CharacterRebirths[10] = store.CharacterRebirthState{CharacterId: 10, RebirthCount: 5}
	s.CharacterRebirths[20] = store.CharacterRebirthState{CharacterId: 20, RebirthCount: 5}
	s.CharacterBoards[2001] = store.CharacterBoardState{CharacterBoardId: 2001, PanelReleaseBit1: 255}
	s.Weapons["w-stage"] = store.WeaponState{UserWeaponUuid: "w-stage", WeaponId: 8, Level: 90, LimitBreakCount: 4}
	s.WeaponSkills["w-stage"] = []store.WeaponSkillState{{UserWeaponUuid: "w-stage", SlotNumber: 1, Level: 15}}
	s.Parts["p-stage"] = store.PartsState{UserPartsUuid: "p-stage", PartsId: 404, Level: 15, PartsStatusMainId: 28}
	s.PartsStatusSubs[store.PartsStatusSubKey{UserPartsUuid: "p-stage", StatusIndex: 1}] = store.PartsStatusSubState{UserPartsUuid: "p-stage", StatusIndex: 1, Level: 15, StatusKindType: 3, StatusCalculationType: 1, StatusChangeValue: 140}
	return u, s
}

var testCharacterOf = map[int32]int32{100: 10, 200: 20, 300: 30}
var testBoards = map[int32][]int32{20: {2001}}

func writeSpec(t *testing.T, raw string) deckWriteSpec {
	t.Helper()
	var spec deckWriteSpec
	if err := json.Unmarshal([]byte(raw), &spec); err != nil {
		t.Fatal(err)
	}
	return spec
}

func apply(u, s *store.UserState, spec deckWriteSpec, limits store.PossessionLimits) error {
	return applyDeckWrite(u, s, spec, deckWriteEnv{limits: limits, characterOf: testCharacterOf, boardsOf: testBoards}, 1000)
}

const newDeck = `{"slots":[{"deck_type":2,"number":2,"power":4321}],
 "characters":[{"costume":{"uuid":"s-200","source":"stage"},"main_weapon":{"uuid":"w-stage","source":"stage"},
                "memoirs":[{"uuid":"p-stage","source":"stage"}]},
               {"costume":{"uuid":"c-own","source":"save"},"main_weapon":{"uuid":"w-own","source":"save"}}],
 "raise":[]}`

func TestDeckWriteOnlySelectedSlots(t *testing.T) {
	u, s := deckWriteStates()
	before := map[store.DeckKey]store.DeckState{}
	for k, v := range u.Decks {
		before[k] = v
	}
	dc := u.DeckCharacters["dc-q"]
	if err := apply(u, s, writeSpec(t, newDeck), store.PossessionLimits{}); err != nil {
		t.Fatal(err)
	}
	for k, v := range before {
		if !reflect.DeepEqual(u.Decks[k], v) {
			t.Fatalf("deck %v changed: %+v", k, u.Decks[k])
		}
	}
	if u.DeckCharacters["dc-q"] != dc {
		t.Fatal("another deck's character changed")
	}
	d := u.Decks[store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: 2}]
	if d.UserDeckCharacterUuid01 == "" || d.UserDeckCharacterUuid02 == "" || d.UserDeckCharacterUuid03 != "" || d.Power != 4321 {
		t.Fatalf("written deck: %+v", d)
	}
}

func TestDeckWriteGrantsRaised(t *testing.T) {
	u, s := deckWriteStates()
	if err := apply(u, s, writeSpec(t, newDeck), store.PossessionLimits{}); err != nil {
		t.Fatal(err)
	}
	d := u.Decks[store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: 2}]
	dc := u.DeckCharacters[d.UserDeckCharacterUuid01]
	c := u.Costumes[dc.UserCostumeUuid]
	if c.CostumeId != 200 || c.Level != 100 || c.AwakenCount != 5 || dc.UserCostumeUuid == "s-200" {
		t.Fatalf("new costume: %+v (deck character %+v)", c, dc)
	}
	if u.CostumeActiveSkills[dc.UserCostumeUuid].Level != 15 {
		t.Fatal("the new costume's skill was not copied")
	}
	if u.CharacterRebirths[20].RebirthCount != 5 || u.CharacterBoards[2001].PanelReleaseBit1 != 255 {
		t.Fatal("a character new to the player did not come fully raised")
	}
	parts := u.DeckParts[d.UserDeckCharacterUuid01]
	if len(parts) != 1 || u.Parts[parts[0]].PartsStatusMainId != 28 || parts[0] == "p-stage" {
		t.Fatalf("memoir: %v %+v", parts, u.Parts)
	}
	if u.PartsStatusSubs[store.PartsStatusSubKey{UserPartsUuid: parts[0], StatusIndex: 1}].StatusChangeValue != 140 {
		t.Fatal("memoir sub stats were not copied")
	}
	if w := u.Weapons[dc.MainUserWeaponUuid]; w.WeaponId != 8 || w.Level != 90 || len(u.WeaponSkills[dc.MainUserWeaponUuid]) != 1 {
		t.Fatalf("weapon: %+v", w)
	}
}

func TestDeckWriteRaisesOnlyTicked(t *testing.T) {
	u, s := deckWriteStates()
	spec := writeSpec(t, newDeck)
	if err := apply(u, s, spec, store.PossessionLimits{}); err != nil {
		t.Fatal(err)
	}
	if u.Costumes["c-own"].Level != 50 {
		t.Fatal("an unticked owned costume was raised")
	}
	u, s = deckWriteStates()
	spec.Raise = []int32{100}
	if err := apply(u, s, spec, store.PossessionLimits{}); err != nil {
		t.Fatal(err)
	}
	c := u.Costumes["c-own"]
	if c.Level != 100 || c.AwakenCount != 5 || c.UserCostumeUuid != "c-own" || u.CharacterRebirths[10].RebirthCount != 5 {
		t.Fatalf("ticked costume: %+v", c)
	}
	if u.Costumes["c-other"].Level != 40 {
		t.Fatal("another costume changed")
	}
}

func TestDeckWriteNeverTouchesOwnedWeapons(t *testing.T) {
	u, s := deckWriteStates()
	if err := apply(u, s, writeSpec(t, newDeck), store.PossessionLimits{}); err != nil {
		t.Fatal(err)
	}
	if u.Weapons["w-own"].Level != 12 {
		t.Fatal("an owned weapon changed")
	}
}

func TestDeckWriteRollsBackOnGrantFailure(t *testing.T) {
	u, s := deckWriteStates()
	before, _ := json.Marshal(u)
	err := apply(u, s, writeSpec(t, newDeck), store.PossessionLimits{Weapon: 1})
	if err == nil || !strings.Contains(err.Error(), "weapon") {
		t.Fatalf("error %v, want one about weapons", err)
	}
	after, _ := json.Marshal(u)
	if string(before) != string(after) {
		t.Fatal("a refused write changed the save")
	}
}

func TestDeckWriteSharedItem(t *testing.T) {
	u, s := deckWriteStates()
	spec := writeSpec(t, `{"slots":[{"deck_type":2,"number":3}],
	 "characters":[{"costume":{"uuid":"c-own","source":"save"},"main_weapon":{"uuid":"w-own","source":"save"}},
	               {"costume":{"uuid":"c-other","source":"save"},"main_weapon":{"uuid":"w-own","source":"save"}}]}`)
	err := apply(u, s, spec, store.PossessionLimits{})
	if err == nil || !strings.Contains(err.Error(), "w-own") && !strings.Contains(err.Error(), "weapon 7") {
		t.Fatalf("error %v, want one naming the shared weapon", err)
	}
	// The same deck written to two slots shares the owned pieces: allowed.
	spec = writeSpec(t, `{"slots":[{"deck_type":2,"number":3},{"deck_type":2,"number":4}],
	 "characters":[{"costume":{"uuid":"c-own","source":"save"},"main_weapon":{"uuid":"w-own","source":"save"}}]}`)
	if err := apply(u, s, spec, store.PossessionLimits{}); err != nil {
		t.Fatal(err)
	}
}

// The game fields a character once per deck.
func TestDeckWriteRefusesACharacterTwice(t *testing.T) {
	u, s := deckWriteStates()
	s.Costumes["s-101"] = store.CostumeState{UserCostumeUuid: "s-101", CostumeId: 101, Level: 100}
	env := deckWriteEnv{characterOf: map[int32]int32{100: 10, 101: 10, 200: 20}, boardsOf: testBoards}
	spec := writeSpec(t, `{"slots":[{"deck_type":2,"number":2}],"characters":[{"costume":{"uuid":"c-own","source":"save"}},{"costume":{"uuid":"s-101","source":"stage"}}]}`)
	before, _ := json.Marshal(u)
	if err := applyDeckWrite(u, s, spec, env, 1000); err == nil || !strings.Contains(err.Error(), "character 10") {
		t.Fatalf("error %v, want one naming character 10", err)
	}
	if after, _ := json.Marshal(u); string(after) != string(before) {
		t.Fatal("a refused write changed the save")
	}
}

// A debris the player owns, staged for two characters, maps twice to the one
// the player holds: refused, naming it, before anything changes.
func TestDeckWriteRefusesOneDebrisOnTwoCharacters(t *testing.T) {
	u, s := deckWriteStates()
	u.Thoughts["t-own"] = store.ThoughtState{UserThoughtUuid: "t-own", ThoughtId: 55}
	s.Thoughts["t-s1"] = store.ThoughtState{UserThoughtUuid: "t-s1", ThoughtId: 55}
	s.Thoughts["t-s2"] = store.ThoughtState{UserThoughtUuid: "t-s2", ThoughtId: 55}
	spec := writeSpec(t, `{"slots":[{"deck_type":2,"number":2}],"characters":[
	 {"costume":{"uuid":"c-own","source":"save"},"debris":{"uuid":"t-s1","source":"stage"}},
	 {"costume":{"uuid":"s-200","source":"stage"},"debris":{"uuid":"t-s2","source":"stage"}}]}`)
	before, _ := json.Marshal(u)
	if err := apply(u, s, spec, store.PossessionLimits{}); err == nil || !strings.Contains(err.Error(), "debris 55") {
		t.Fatalf("error %v, want one naming debris 55", err)
	}
	if after, _ := json.Marshal(u); string(after) != string(before) {
		t.Fatal("a refused write changed the save")
	}
}

func TestDeckWriteOwnedCostumeFromStageIsNotDuplicated(t *testing.T) {
	u, s := deckWriteStates()
	spec := writeSpec(t, `{"slots":[{"deck_type":2,"number":2}],"characters":[{"costume":{"uuid":"s-100","source":"stage"}}]}`)
	if err := apply(u, s, spec, store.PossessionLimits{}); err != nil {
		t.Fatal(err)
	}
	n := 0
	for _, c := range u.Costumes {
		if c.CostumeId == 100 {
			n++
		}
	}
	d := u.Decks[store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: 2}]
	if n != 1 || u.DeckCharacters[d.UserDeckCharacterUuid01].UserCostumeUuid != "c-own" || u.Costumes["c-own"].Level != 50 {
		t.Fatal("an owned costume was duplicated or raised without a tick")
	}
}

// A character may carry its own karma (the Force list's, chosen for Force): the copied costume gets it, slot by
// slot, in place of the staged costume's; the stage keeps its own.
func TestDeckWriteKarmaOverride(t *testing.T) {
	u, s := deckWriteStates()
	if s.CostumeLotteryEffects == nil {
		s.CostumeLotteryEffects = map[store.CostumeLotteryEffectKey]store.CostumeLotteryEffectState{}
	}
	if u.CostumeLotteryEffects == nil {
		u.CostumeLotteryEffects = map[store.CostumeLotteryEffectKey]store.CostumeLotteryEffectState{}
	}
	for slot := int32(1); slot <= 3; slot++ {
		k := store.CostumeLotteryEffectKey{UserCostumeUuid: "s-100", SlotNumber: slot}
		s.CostumeLotteryEffects[k] = store.CostumeLotteryEffectState{UserCostumeUuid: "s-100", SlotNumber: slot, OddsNumber: 1}
	}
	u.Costumes = map[string]store.CostumeState{} // the player does not own costume 100
	spec := writeSpec(t, `{"slots":[{"deck_type":1,"number":3,"power":1}],
 "characters":[{"costume":{"uuid":"s-100","source":"stage"},"karma":{"1":5,"3":7}}],"raise":[]}`)
	if err := apply(u, s, spec, store.PossessionLimits{}); err != nil {
		t.Fatal(err)
	}
	var to string
	for k, c := range u.Costumes {
		if c.CostumeId == 100 {
			to = k
		}
	}
	got := map[int32]int32{}
	for k, x := range u.CostumeLotteryEffects {
		if k.UserCostumeUuid == to {
			got[k.SlotNumber] = x.OddsNumber
		}
	}
	if !reflect.DeepEqual(got, map[int32]int32{1: 5, 2: 1, 3: 7}) {
		t.Fatalf("written karma %v", got)
	}
	if s.CostumeLotteryEffects[store.CostumeLotteryEffectKey{UserCostumeUuid: "s-100", SlotNumber: 1}].OddsNumber != 1 {
		t.Fatal("the stage's karma changed")
	}
}
