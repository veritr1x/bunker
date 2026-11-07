package pvp

// Pod Programs › Mods › Friends from the story: the first ladder slots become
// characters from the story, each leading their deck with their own costume.
// They count as friends while the mod is on (FriendIds), without being
// written to the save, and appear in the Arena at their slots' points, so
// ranks stay as they were. Off, everything is as before.

import (
	"slices"

	"lunar-tear/server/internal/mods"
	"lunar-tear/server/internal/store"
)

// StoryCharacters are the story friends, in ladder slot order (names as the
// game's character.name texts).
var StoryCharacters = []struct {
	CharacterId int32
	Name        string
}{
	{1001, "2B"}, {1002, "9S"}, {1003, "A2"}, {1004, "Levania"}, {1006, "Argo"}, {1007, "Dimos"}, {1008, "Rion"},
	{1009, "Gayle"}, {1010, "Noelle"}, {1011, "063y"}, {1012, "F66x"}, {1013, "Lars"}, {1014, "Griff"}, {1015, "Akeha"},
	{1017, "Emil"}, {1018, "Kainé"}, {1019, "Fio"}, {1020, "Hina"}, {1021, "Yuzuki"}, {1022, "Saryu"}, {1023, "Priyet"},
	{1024, "Marie"}, {1025, "Yurie"}, {1026, "Sarafa"}, {1027, "Yudil"}, {1031, "Zero"}, {1048, "10H"},
}

func storyOn() bool { return mods.Get().StoryFriends }

// storyIds are the story friends' player ids.
func storyIds() []int64 {
	ids := make([]int64, len(StoryCharacters))
	for i := range StoryCharacters {
		ids[i] = CpuIdBase + int64(i) + 1
	}
	return ids
}

// FriendIds is the player's friends: the save's, then the story friends while
// the mod is on, in the places the friend limit leaves free.
func FriendIds(f *store.FriendState) []int64 {
	if !storyOn() {
		return f.Friends
	}
	out := slices.Clone(f.Friends)
	limit := friendLimit()
	for _, id := range storyIds() {
		if len(out) >= limit {
			break
		}
		if !slices.Contains(out, id) {
			out = append(out, id)
		}
	}
	return out
}

// friendLimit is the game's friend limit (m_config), 100 without a catalog.
func friendLimit() int {
	if c := Current(); c != nil && c.Friend.Friends > 0 {
		return c.Friend.Friends
	}
	return 100
}

// StoryCPU is story friend i of a season's ladder.
func (c *Catalog) StoryCPU(i int, seasonId int32) CPU {
	return c.Ladder(seasonId).story[i]
}

// storyCPU turns a ladder slot into a story character: their name, and their
// strongest costume (highest rarity, then newest) leading with its weapon.
// Another slot holding the same character gets another character's costume.
func (c *Catalog) storyCPU(base CPU, characterId int32, name string) CPU {
	cpu := base
	cpu.Name = name
	lead := costumePick{}
	for _, p := range c.costumes {
		if p.CharacterId == characterId && (p.Rarity > lead.Rarity || p.Rarity == lead.Rarity && p.CostumeId > lead.CostumeId) {
			lead = p
		}
	}
	if lead.CostumeId == 0 {
		return cpu
	}
	cpu.Costumes[0], cpu.Weapons[0] = lead.CostumeId, c.weaponFor(lead)
	characterOf := map[int32]int32{}
	for _, p := range c.costumes {
		characterOf[p.CostumeId] = p.CharacterId
	}
	used := map[int32]bool{characterId: true}
	for slot := 1; slot < 3; slot++ {
		if cpu.Costumes[slot] == 0 {
			continue
		}
		if ch := characterOf[cpu.Costumes[slot]]; !used[ch] {
			used[ch] = true
			continue
		}
		for _, p := range c.costumes {
			if !used[p.CharacterId] {
				used[p.CharacterId] = true
				cpu.Costumes[slot], cpu.Weapons[slot] = p.CostumeId, c.weaponFor(p)
				break
			}
		}
	}
	return cpu
}

// weaponFor is a costume's paired weapon, else one of its rarity.
func (c *Catalog) weaponFor(p costumePick) int32 {
	if w, ok := c.pairs[p.CostumeId]; ok {
		return w
	}
	if list := c.weapons[p.Rarity]; len(list) > 0 {
		return list[0]
	}
	return 0
}

// at is ladder slot i as the mods make it.
func (l *Ladder) at(i int) CPU {
	if i < len(l.story) && storyOn() {
		return l.story[i]
	}
	return l.cpus[i]
}
