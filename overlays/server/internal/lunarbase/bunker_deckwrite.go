package lunarbase

// Pod Programs › Deck Builder writes a deck into the player's save
// ("deck_write"), copying exactly what the page showed:
//
//   - pieces from the staging save (fully raised by the server's own
//     upgrades, see bunker_deckbuilder.go) are added as new pieces, one copy
//     per use; a costume or debris the player already owns is used instead of
//     a second copy (the game holds one of each);
//   - a character new to the player comes with its rank and Mythic Slab rows;
//   - an owned costume changes only when the player ticked it ("raise"): it
//     then takes the staged values, keeping its own uuid, with its
//     character's rank and board;
//   - only the selected deck slots are replaced.
//
// Everything is checked before anything changes, so a refused write leaves
// the save as it was.

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"slices"
	"strconv"

	"github.com/google/uuid"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/masterdata/memorydb"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/questflow"
	"lunar-tear/server/internal/store"
)

type pieceRef struct {
	UUID   string `json:"uuid"`
	Source string `json:"source"` // "save" (the player's) or "stage"
}

type deckCharSpec struct {
	Costume    pieceRef   `json:"costume"`
	MainWeapon *pieceRef  `json:"main_weapon"`
	Subs       []pieceRef `json:"subs"`
	Companion  *pieceRef  `json:"companion"`
	Memoirs    []pieceRef `json:"memoirs"`
	Debris     *pieceRef  `json:"debris"`
	// Karma {slot: odds number} for a costume copied from the stage, in place of the staged costume's (Deck
	// Builder's Force list chooses karma for Force); a costume the player owns keeps theirs.
	Karma map[string]int32 `json:"karma"`
}

type deckSlotSpec struct {
	DeckType int32 `json:"deck_type"`
	Number   int32 `json:"number"`
	Power    int32 `json:"power"`
}

type deckWriteSpec struct {
	Slots      []deckSlotSpec  `json:"slots"`
	Characters []*deckCharSpec `json:"characters"` // left, middle, right; null = empty
	Raise      []int32         `json:"raise"`      // owned costume ids the player ticked
}

type deckWriteEnv struct {
	limits      store.PossessionLimits
	characterOf map[int32]int32   // costume id -> character id
	boardsOf    map[int32][]int32 // character id -> Mythic Slab board ids
}

func (s deckCharSpec) refs() []struct {
	kind string
	ref  pieceRef
} {
	var out []struct {
		kind string
		ref  pieceRef
	}
	add := func(kind string, r *pieceRef) {
		if r != nil && r.UUID != "" {
			out = append(out, struct {
				kind string
				ref  pieceRef
			}{kind, *r})
		}
	}
	add("costume", &s.Costume)
	add("weapon", s.MainWeapon)
	for i := range s.Subs {
		add("weapon", &s.Subs[i])
	}
	add("companion", s.Companion)
	for i := range s.Memoirs {
		add("memoir", &s.Memoirs[i])
	}
	add("debris", s.Debris)
	return out
}

func held(u *store.UserState, kind, id string) (int32, bool) {
	switch kind {
	case "costume":
		c, ok := u.Costumes[id]
		return c.CostumeId, ok
	case "weapon":
		w, ok := u.Weapons[id]
		return w.WeaponId, ok
	case "companion":
		c, ok := u.Companions[id]
		return c.CompanionId, ok
	case "memoir":
		p, ok := u.Parts[id]
		return p.PartsId, ok
	case "debris":
		t, ok := u.Thoughts[id]
		return t.ThoughtId, ok
	}
	return 0, false
}

func ownedCostume(u *store.UserState, costumeId int32) (string, bool) {
	for k, c := range u.Costumes {
		if c.CostumeId == costumeId {
			return k, true
		}
	}
	return "", false
}

func ownedThought(u *store.UserState, thoughtId int32) (string, bool) {
	for k, t := range u.Thoughts {
		if t.ThoughtId == thoughtId {
			return k, true
		}
	}
	return "", false
}

// applyDeckWrite checks the whole write, then makes it.
func applyDeckWrite(u, stage *store.UserState, spec deckWriteSpec, env deckWriteEnv, now int64) error {
	if len(spec.Slots) == 0 {
		return errors.New("choose a deck slot to write to")
	}
	if len(spec.Characters) == 0 || len(spec.Characters) > 3 {
		return errors.New("a deck has one to three characters")
	}
	newWeapons, newParts := 0, 0
	seen := map[string]bool{}
	for _, c := range spec.Characters {
		if c == nil {
			continue
		}
		if c.Costume.UUID == "" {
			return errors.New("a character has no costume")
		}
		for _, r := range c.refs() {
			from := u
			if r.ref.Source == "stage" {
				if stage == nil {
					return errors.New("the Deck Builder stage is not ready")
				}
				from = stage
			}
			id, ok := held(from, r.kind, r.ref.UUID)
			if !ok {
				return fmt.Errorf("%s %s is not in the %s", r.kind, r.ref.UUID, map[bool]string{true: "stage", false: "save"}[r.ref.Source == "stage"])
			}
			if r.ref.Source == "save" {
				key := r.kind + ":" + r.ref.UUID
				if seen[key] {
					return fmt.Errorf("the deck uses %s %d (%s) twice", r.kind, id, r.ref.UUID)
				}
				seen[key] = true
				continue
			}
			switch r.kind {
			case "weapon":
				newWeapons++
			case "memoir":
				newParts++
			}
		}
	}
	// One character once per deck, and a costume or debris (the game holds one
	// of each) on one character only, counting staged ones as the owned ones
	// they map to.
	characters, unique := map[int32]bool{}, map[string]bool{}
	for _, c := range spec.Characters {
		if c == nil {
			continue
		}
		for _, r := range c.refs() {
			if r.kind != "costume" && r.kind != "debris" {
				continue
			}
			from := u
			if r.ref.Source == "stage" {
				from = stage
			}
			id, _ := held(from, r.kind, r.ref.UUID)
			if r.kind == "costume" {
				ch, ok := env.characterOf[id]
				if !ok {
					ch = id
				}
				if characters[ch] {
					return fmt.Errorf("the deck has character %d twice; the game fields a character once", ch)
				}
				characters[ch] = true
			}
			key := fmt.Sprintf("%s %d", r.kind, id)
			if unique[key] {
				return fmt.Errorf("the deck puts %s on two characters; you can hold only one", key)
			}
			unique[key] = true
		}
	}
	if env.limits.Weapon > 0 && len(u.Weapons)+newWeapons > int(env.limits.Weapon) {
		return fmt.Errorf("not enough room for weapons: %d more would pass the limit of %d (you hold %d)", newWeapons, env.limits.Weapon, len(u.Weapons))
	}
	partsCap := memoirInventoryCap
	if env.limits.Parts > 0 {
		partsCap = int(env.limits.Parts)
	}
	if len(u.Parts)+newParts > partsCap {
		return fmt.Errorf("not enough room for memoirs: %d more would pass the limit of %d (you hold %d)", newParts, partsCap, len(u.Parts))
	}
	for _, id := range spec.Raise {
		if _, ok := ownedCostume(u, id); !ok {
			return fmt.Errorf("costume %d to raise is not owned", id)
		}
	}

	// ---- write ----
	uuids := make([][]string, len(spec.Characters)) // per character, per ref: the uuid in the save
	for i, c := range spec.Characters {
		if c == nil {
			continue
		}
		for _, r := range c.refs() {
			if r.ref.Source == "save" {
				uuids[i] = append(uuids[i], r.ref.UUID)
				continue
			}
			_, owned := ownedCostume(u, stage.Costumes[r.ref.UUID].CostumeId)
			to := copyPiece(u, stage, r.kind, r.ref.UUID, env, now)
			uuids[i] = append(uuids[i], to)
			if r.kind == "costume" && !owned && len(c.Karma) > 0 {
				setKarma(u, to, c.Karma, now)
			}
		}
	}
	for _, id := range spec.Raise {
		raiseCostume(u, stage, id, env, now)
	}
	for _, slot := range spec.Slots {
		writeDeck(u, slot, spec.Characters, uuids, now)
	}
	return nil
}

func copyPiece(u, s *store.UserState, kind, from string, env deckWriteEnv, now int64) string {
	switch kind {
	case "costume":
		c := s.Costumes[from]
		if mine, ok := ownedCostume(u, c.CostumeId); ok {
			return mine
		}
		to := uuid.New().String()
		copyCostumeRows(u, s, from, to, now)
		c.UserCostumeUuid, c.AcquisitionDatetime, c.LatestVersion = to, now, now
		u.Costumes[to] = c
		if ch, ok := env.characterOf[c.CostumeId]; ok {
			if _, has := u.Characters[ch]; !has {
				copyCharacterRows(u, s, ch, env, now)
			}
		}
		return to
	case "weapon":
		w := s.Weapons[from]
		to := uuid.New().String()
		w.UserWeaponUuid, w.AcquisitionDatetime, w.LatestVersion = to, now, now
		u.Weapons[to] = w
		for _, x := range s.WeaponSkills[from] {
			x.UserWeaponUuid = to
			u.WeaponSkills[to] = append(u.WeaponSkills[to], x)
		}
		for _, x := range s.WeaponAbilities[from] {
			x.UserWeaponUuid = to
			u.WeaponAbilities[to] = append(u.WeaponAbilities[to], x)
		}
		if a, ok := s.WeaponAwakens[from]; ok {
			a.UserWeaponUuid, a.LatestVersion = to, now
			u.WeaponAwakens[to] = a
		}
		note := u.WeaponNotes[w.WeaponId]
		if note.WeaponId == 0 {
			note = store.WeaponNoteState{WeaponId: w.WeaponId, FirstAcquisitionDatetime: now}
		}
		note.MaxLevel = max(note.MaxLevel, w.Level)
		note.MaxLimitBreakCount = max(note.MaxLimitBreakCount, w.LimitBreakCount)
		note.LatestVersion = now
		u.WeaponNotes[w.WeaponId] = note
		return to
	case "companion":
		c := s.Companions[from]
		to := uuid.New().String()
		c.UserCompanionUuid, c.AcquisitionDatetime, c.LatestVersion = to, now, now
		u.Companions[to] = c
		return to
	case "memoir":
		p := s.Parts[from]
		to := uuid.New().String()
		p.UserPartsUuid, p.AcquisitionDatetime, p.LatestVersion = to, now, now
		u.Parts[to] = p
		for k, x := range s.PartsStatusSubs {
			if k.UserPartsUuid == from {
				x.UserPartsUuid, x.LatestVersion = to, now
				u.PartsStatusSubs[store.PartsStatusSubKey{UserPartsUuid: to, StatusIndex: k.StatusIndex}] = x
			}
		}
		return to
	case "debris":
		t := s.Thoughts[from]
		if mine, ok := ownedThought(u, t.ThoughtId); ok {
			return mine
		}
		to := uuid.New().String()
		t.UserThoughtUuid, t.AcquisitionDatetime, t.LatestVersion = to, now, now
		u.Thoughts[to] = t
		return to
	}
	return ""
}

// setKarma sets costume uuid's karma slots ({slot: odds number}) in u.
func setKarma(u *store.UserState, uuid string, karma map[string]int32, now int64) {
	for slot, odds := range karma {
		n, err := strconv.Atoi(slot)
		if err != nil {
			continue
		}
		k := store.CostumeLotteryEffectKey{UserCostumeUuid: uuid, SlotNumber: int32(n)}
		u.CostumeLotteryEffects[k] = store.CostumeLotteryEffectState{UserCostumeUuid: uuid, SlotNumber: int32(n), OddsNumber: odds, LatestVersion: now}
	}
}

// copyCostumeRows gives costume `to` in u the staged costume's skill,
// awakening statuses and karma.
func copyCostumeRows(u, s *store.UserState, from, to string, now int64) {
	if a, ok := s.CostumeActiveSkills[from]; ok {
		a.UserCostumeUuid, a.LatestVersion = to, now
		u.CostumeActiveSkills[to] = a
	}
	for k := range u.CostumeAwakenStatusUps {
		if k.UserCostumeUuid == to {
			delete(u.CostumeAwakenStatusUps, k)
		}
	}
	for k, x := range s.CostumeAwakenStatusUps {
		if k.UserCostumeUuid == from {
			x.UserCostumeUuid = to
			u.CostumeAwakenStatusUps[store.CostumeAwakenStatusKey{UserCostumeUuid: to, StatusCalculationType: k.StatusCalculationType}] = x
		}
	}
	for k := range u.CostumeLotteryEffects {
		if k.UserCostumeUuid == to {
			delete(u.CostumeLotteryEffects, k)
		}
	}
	for k, x := range s.CostumeLotteryEffects {
		if k.UserCostumeUuid == from {
			x.UserCostumeUuid, x.LatestVersion = to, now
			u.CostumeLotteryEffects[store.CostumeLotteryEffectKey{UserCostumeUuid: to, SlotNumber: k.SlotNumber}] = x
		}
	}
}

// copyCharacterRows gives u the staged character's rank and Mythic Slab.
func copyCharacterRows(u, s *store.UserState, ch int32, env deckWriteEnv, now int64) {
	if c, ok := s.Characters[ch]; ok {
		if _, has := u.Characters[ch]; !has {
			c.LatestVersion = now
			u.Characters[ch] = c
		}
	}
	if r, ok := s.CharacterRebirths[ch]; ok {
		r.LatestVersion = now
		u.CharacterRebirths[ch] = r
	}
	for k, x := range s.CharacterBoardAbilities {
		if k.CharacterId == ch {
			u.CharacterBoardAbilities[k] = x
		}
	}
	for k, x := range s.CharacterBoardStatusUps {
		if k.CharacterId == ch {
			u.CharacterBoardStatusUps[k] = x
		}
	}
	for _, b := range env.boardsOf[ch] {
		if x, ok := s.CharacterBoards[b]; ok {
			u.CharacterBoards[b] = x
		}
	}
}

func raiseCostume(u, s *store.UserState, costumeId int32, env deckWriteEnv, now int64) {
	mine, _ := ownedCostume(u, costumeId)
	var from string
	for k, c := range s.Costumes {
		if c.CostumeId == costumeId {
			from = k
		}
	}
	if from == "" {
		return
	}
	c, t := u.Costumes[mine], s.Costumes[from]
	c.Level, c.Exp, c.LimitBreakCount, c.AwakenCount = t.Level, t.Exp, t.LimitBreakCount, t.AwakenCount
	c.CostumeLotteryEffectUnlockedSlotCount, c.LatestVersion = t.CostumeLotteryEffectUnlockedSlotCount, now
	u.Costumes[mine] = c
	copyCostumeRows(u, s, from, mine, now)
	if ch, ok := env.characterOf[costumeId]; ok {
		copyCharacterRows(u, s, ch, env, now)
	}
}

func writeDeck(u *store.UserState, slot deckSlotSpec, chars []*deckCharSpec, uuids [][]string, now int64) {
	key := store.DeckKey{DeckType: model.DeckType(slot.DeckType), UserDeckNumber: slot.Number}
	old := u.Decks[key]
	for _, dc := range []string{old.UserDeckCharacterUuid01, old.UserDeckCharacterUuid02, old.UserDeckCharacterUuid03} {
		if dc != "" {
			delete(u.DeckCharacters, dc)
			delete(u.DeckSubWeapons, dc)
			delete(u.DeckParts, dc)
		}
	}
	slots := [3]string{}
	for i, c := range chars {
		if c == nil || i >= 3 {
			continue
		}
		ids := uuids[i]
		next := 0
		take := func() string { v := ids[next]; next++; return v }
		dc := store.DeckCharacterState{UserDeckCharacterUuid: uuid.New().String(), LatestVersion: now}
		dc.UserCostumeUuid = take()
		if c.MainWeapon != nil && c.MainWeapon.UUID != "" {
			dc.MainUserWeaponUuid = take()
		}
		var subs []string
		for range c.Subs {
			subs = append(subs, take())
		}
		if c.Companion != nil && c.Companion.UUID != "" {
			dc.UserCompanionUuid = take()
		}
		var parts []string
		for range c.Memoirs {
			parts = append(parts, take())
		}
		if c.Debris != nil && c.Debris.UUID != "" {
			dc.UserThoughtUuid = take()
		}
		u.DeckCharacters[dc.UserDeckCharacterUuid] = dc
		if len(subs) > 0 {
			u.DeckSubWeapons[dc.UserDeckCharacterUuid] = subs
		}
		if len(parts) > 0 {
			u.DeckParts[dc.UserDeckCharacterUuid] = parts
		}
		slots[i] = dc.UserDeckCharacterUuid
	}
	name := old.Name
	if name == "" {
		name = "Deck Builder"
	}
	u.Decks[key] = store.DeckState{DeckType: key.DeckType, UserDeckNumber: key.UserDeckNumber, UserDeckCharacterUuid01: slots[0],
		UserDeckCharacterUuid02: slots[1], UserDeckCharacterUuid03: slots[2], Name: name, Power: slot.Power, LatestVersion: now}
}

// ---------------------------------------------------------------- the action

// runDeckWrite: "deck_write" with "deck" (deckWriteSpec) and "stage_path"
// (set by the caller: the Android bridge fixes it to the app's stage).
func runDeckWrite(req *request) (int, error) {
	var spec deckWriteSpec
	if err := json.Unmarshal(req.Deck, &spec); err != nil {
		return 0, fmt.Errorf("deck: %w", err)
	}
	if req.MasterDataPath == "" {
		return 0, errors.New("master_data_path required for deck_write")
	}
	if err := memorydb.Init(req.MasterDataPath); err != nil {
		return 0, fmt.Errorf("init master data: %w", err)
	}
	env, err := deckWriteEnvironment()
	if err != nil {
		return 0, err
	}
	var stage *store.UserState
	if _, serr := os.Stat(req.StagePath); req.StagePath != "" && serr == nil { // never create a missing stage
		sdb, sst, err := openDB(req.StagePath)
		if err != nil {
			return 0, err
		}
		s, err := sst.LoadUser(1)
		sdb.Close()
		if err != nil {
			return 0, fmt.Errorf("stage: %w", err)
		}
		stage = &s
	}
	db, st, err := openDB(req.DBPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	now := giftNow()
	var werr error
	_, err = st.UpdateUser(req.UserID, func(u *store.UserState) {
		werr = applyDeckWrite(u, stage, spec, env, now)
	})
	if werr != nil {
		return 0, werr
	}
	if err != nil {
		return 0, fmt.Errorf("deck write: %w", err)
	}
	return len(spec.Slots), nil
}

func deckWriteEnvironment() (deckWriteEnv, error) {
	partsCatalog, err := masterdata.LoadPartsCatalog()
	if err != nil {
		return deckWriteEnv{}, err
	}
	catalog, err := masterdata.LoadQuestCatalog(partsCatalog)
	if err != nil {
		return deckWriteEnv{}, err
	}
	gameConfig, err := masterdata.LoadGameConfig()
	if err != nil {
		return deckWriteEnv{}, err
	}
	granter := questflow.BuildGranter(catalog, gameConfig)
	env := deckWriteEnv{limits: granter.Limits, characterOf: map[int32]int32{}, boardsOf: map[int32][]int32{}}
	costumes, err := memorydb.ReadTable[masterdata.EntityMCostume]("m_costume")
	if err != nil {
		return env, err
	}
	for _, c := range costumes {
		env.characterOf[c.CostumeId] = c.CharacterId
	}
	assign, _ := memorydb.ReadTable[masterdata.EntityMCharacterBoardAssignment]("m_character_board_assignment")
	groups, _ := memorydb.ReadTable[masterdata.EntityMCharacterBoardGroup]("m_character_board_group")
	boards, _ := memorydb.ReadTable[masterdata.EntityMCharacterBoard]("m_character_board")
	for _, a := range assign {
		for _, g := range groups {
			if g.CharacterBoardCategoryId != a.CharacterBoardCategoryId {
				continue
			}
			for _, b := range boards {
				if b.CharacterBoardGroupId == g.CharacterBoardGroupId && !slices.Contains(env.boardsOf[a.CharacterId], b.CharacterBoardId) {
					env.boardsOf[a.CharacterId] = append(env.boardsOf[a.CharacterId], b.CharacterBoardId)
				}
			}
		}
	}
	return env, nil
}
