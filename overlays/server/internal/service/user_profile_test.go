package service

import (
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func TestLatestUsedDeck(t *testing.T) {
	u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	addDeck := func(dt model.DeckType, number, power int32, costumes ...int32) {
		d := store.DeckState{DeckType: dt, UserDeckNumber: number, Power: power}
		slots := []*string{&d.UserDeckCharacterUuid01, &d.UserDeckCharacterUuid02, &d.UserDeckCharacterUuid03}
		for i, co := range costumes {
			id := string(rune('a'+number)) + string(rune('0'+i))
			u.Costumes["c"+id] = store.CostumeState{UserCostumeUuid: "c" + id, CostumeId: co}
			u.Weapons["w"+id] = store.WeaponState{UserWeaponUuid: "w" + id, WeaponId: co + 1, Level: 7}
			u.DeckCharacters[id] = store.DeckCharacterState{UserDeckCharacterUuid: id, UserCostumeUuid: "c" + id, MainUserWeaponUuid: "w" + id}
			*slots[i] = id
		}
		u.Decks[store.DeckKey{DeckType: dt, UserDeckNumber: number}] = d
	}
	addDeck(model.DeckTypeQuest, 1, 1000, 10100)
	addDeck(model.DeckTypeQuest, 2, 2000, 10200, 10300, 10400)
	addDeck(model.DeckTypeRestrictedQuest, 2, 3000, 10500)

	// No battle recorded yet: the deck of the quest started last.
	u.Quests[1] = store.UserQuestState{QuestId: 1, UserDeckNumber: 1, LatestStartDatetime: 10}
	u.Quests[2] = store.UserQuestState{QuestId: 2, UserDeckNumber: 2, LatestStartDatetime: 20}
	d := latestUsedDeck(u)
	if d.Power != 2000 || len(d.DeckCharacter) != 3 || d.DeckCharacter[1].CostumeId != 10300 ||
		d.DeckCharacter[1].MainWeaponId != 10301 || d.DeckCharacter[1].MainWeaponLevel != 7 {
		t.Fatalf("deck of the last quest: %+v", d)
	}
	// The deck of the last battle, whatever its type.
	u.Ext.LastDeck = store.LastDeckState{DeckType: int32(model.DeckTypeRestrictedQuest), UserDeckNumber: 2}
	if d := latestUsedDeck(u); d.Power != 3000 || len(d.DeckCharacter) != 1 || d.DeckCharacter[0].CostumeId != 10500 {
		t.Fatalf("deck of the last battle: %+v", d)
	}
}
