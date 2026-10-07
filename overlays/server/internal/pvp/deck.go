package pvp

import (
	"math"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Profile is how far the player has raised a deck, averaged over its
// characters. Computer players' characters are raised to a share of it.
type Profile struct {
	Power                                               int32
	CostumeLevel, CostumeLB, SkillLevel, CharacterLevel float64
	WeaponLevel, WeaponLB, WeaponSkill, WeaponAbility   float64
}

// deckFor is the deck to measure: the asked one, else the first Arena or quest deck with characters.
func deckFor(u *store.UserState, key store.DeckKey) (store.DeckState, bool) {
	if d, ok := u.Decks[key]; ok && d.UserDeckCharacterUuid01 != "" {
		return d, true
	}
	for _, k := range []store.DeckKey{{DeckType: model.DeckTypePvp, UserDeckNumber: 1}, {DeckType: model.DeckTypeQuest, UserDeckNumber: 1}} {
		if d, ok := u.Decks[k]; ok && d.UserDeckCharacterUuid01 != "" {
			return d, true
		}
	}
	return store.DeckState{}, false
}

// ProfileOf measures one of the player's decks.
func (c *Catalog) ProfileOf(u *store.UserState, key store.DeckKey) Profile {
	p := Profile{CostumeLevel: 1, SkillLevel: 1, CharacterLevel: 1, WeaponLevel: 1, WeaponSkill: 1, WeaponAbility: 1}
	deck, ok := deckFor(u, key)
	if !ok {
		return p
	}
	var n, cl, clb, sk, chl, wl, wlb, ws, wa, wsn, wan float64
	for _, uuid := range []string{deck.UserDeckCharacterUuid01, deck.UserDeckCharacterUuid02, deck.UserDeckCharacterUuid03} {
		dc, ok := u.DeckCharacters[uuid]
		if !ok || uuid == "" {
			continue
		}
		co, ok := u.Costumes[dc.UserCostumeUuid]
		if !ok {
			continue
		}
		n++
		cl += float64(co.Level)
		clb += float64(co.LimitBreakCount)
		sk += float64(max(1, u.CostumeActiveSkills[dc.UserCostumeUuid].Level))
		if c.cats.Costume != nil {
			chl += float64(max(1, u.Characters[c.cats.Costume.Costumes[co.CostumeId].CharacterId].Level))
		} else {
			chl++
		}
		if w, ok := u.Weapons[dc.MainUserWeaponUuid]; ok {
			wl += float64(w.Level)
			wlb += float64(w.LimitBreakCount)
		} else {
			wl++
		}
		for _, s := range u.WeaponSkills[dc.MainUserWeaponUuid] {
			ws += float64(s.Level)
			wsn++
		}
		for _, a := range u.WeaponAbilities[dc.MainUserWeaponUuid] {
			wa += float64(a.Level)
			wan++
		}
	}
	if n == 0 {
		return p
	}
	p.Power = deck.Power
	p.CostumeLevel, p.CostumeLB, p.SkillLevel, p.CharacterLevel = cl/n, clb/n, sk/n, chl/n
	p.WeaponLevel, p.WeaponLB = wl/n, wlb/n
	if wsn > 0 {
		p.WeaponSkill = ws / wsn
	}
	if wan > 0 {
		p.WeaponAbility = wa / wan
	}
	return p
}

// Strength is how strong a computer player is next to the player: 1 is
// even; those with more points are stronger.
func Strength(cpuPoint, playerPoint int32) float64 {
	return math.Max(0.8, math.Min(1.25, 1+float64(cpuPoint-playerPoint)/20000))
}

// DeckPower is the power shown for a computer player.
func DeckPower(p Profile, strength float64) int32 {
	power := float64(p.Power)
	if power <= 0 {
		power = 3000
	}
	return int32(math.Round(power * strength))
}

func scaled(v, strength float64, lo, hi int32) int32 {
	x := int32(math.Round(v * strength))
	if hi < lo {
		hi = lo
	}
	return max(lo, min(hi, x))
}

// Deck builds the computer player's deck for the battle.
func (c *Catalog) Deck(cpu CPU, p Profile, strength float64) []*pb.PvpDeckCharacter {
	var out []*pb.PvpDeckCharacter
	for slot := range cpu.Costumes {
		if cpu.Costumes[slot] == 0 {
			continue
		}
		// No companion or thought, sent as empty messages like a player without them:
		// the game reads these fields without checking for absent ones.
		out = append(out, &pb.PvpDeckCharacter{
			Costume:    c.costumeInfo(cpu.Costumes[slot], p, strength),
			Companion:  &pb.CompanionInfo{},
			MainWeapon: c.weaponInfo(cpu.Weapons[slot], p, strength),
			Thought:    &pb.ThoughtInfo{},
		})
	}
	return out
}

func (c *Catalog) costumeInfo(id int32, p Profile, strength float64) *pb.CostumeInfo {
	info := &pb.CostumeInfo{CostumeId: id, Level: 1, ActiveSkillLevel: 1, CharacterLevel: 1}
	cc := c.cats.Costume
	if cc == nil {
		return info
	}
	cm, ok := cc.Costumes[id]
	if !ok {
		return info
	}
	info.LimitBreakCount = scaled(p.CostumeLB, strength, 0, 4)
	maxLevel := int32(90)
	if f, ok := cc.MaxLevelByRarity[cm.RarityType]; ok {
		maxLevel = f.Evaluate(info.LimitBreakCount)
	}
	info.Level = scaled(p.CostumeLevel, strength, 1, maxLevel)
	skillMax := int32(15)
	if f, ok := cc.ActiveSkillMaxLevelByRarity[cm.RarityType]; ok {
		skillMax = f.Evaluate(1)
	}
	info.ActiveSkillLevel = scaled(p.SkillLevel, strength, 1, skillMax)
	info.CharacterLevel = scaled(p.CharacterLevel, strength, 1, 999)
	return info
}

func (c *Catalog) weaponInfo(id int32, p Profile, strength float64) *pb.WeaponInfo {
	// The game reads the awaken ability without checking for an absent one
	// (CalculatorDataBattleDeckForPvp.SetWeaponAwakenInfo); ability 0 is none.
	info := &pb.WeaponInfo{WeaponId: id, Level: 1, WeaponAwakenAbility: &pb.AwakenAbilityInfo{}}
	wc := c.cats.Weapon
	if wc == nil || id == 0 {
		return info
	}
	wm, ok := wc.Weapons[id]
	if !ok {
		return info
	}
	info.LimitBreakCount = scaled(p.WeaponLB, strength, 0, 4)
	maxLevel := int32(90)
	if f, ok := wc.MaxLevelByEnhanceId[wm.WeaponSpecificEnhanceId]; ok {
		maxLevel = f.Evaluate(info.LimitBreakCount)
	}
	info.Level = scaled(p.WeaponLevel, strength, 1, maxLevel)
	skillMax, abilityMax := int32(15), int32(15)
	if f, ok := wc.SkillMaxLevelByEnhanceId[wm.WeaponSpecificEnhanceId]; ok {
		skillMax = f.Evaluate(info.LimitBreakCount)
	}
	if f, ok := wc.AbilityMaxLevelByEnhanceId[wm.WeaponSpecificEnhanceId]; ok {
		abilityMax = f.Evaluate(info.LimitBreakCount)
	}
	for _, s := range wc.SkillGroupsByGroupId[wm.WeaponSkillGroupId] {
		info.WeaponSkill = append(info.WeaponSkill, &pb.WeaponSkillInfo{SkillId: s.SkillId, Level: scaled(p.WeaponSkill, strength, 1, skillMax)})
	}
	for _, a := range wc.AbilityGroupsByGroupId[wm.WeaponAbilityGroupId] {
		info.WeaponAbility = append(info.WeaponAbility, &pb.WeaponAbilityInfo{AbilityId: a.AbilityId, Level: scaled(p.WeaponAbility, strength, 1, abilityMax)})
	}
	return info
}

// MainWeaponAttributes are the elements of a computer player's weapons, for the matching list.
func (c *Catalog) MainWeaponAttributes(cpu CPU) []int32 {
	var out []int32
	for _, w := range cpu.Weapons {
		if wm, ok := c.weapon[w]; ok {
			out = append(out, wm.AttributeType)
		}
	}
	return out
}
