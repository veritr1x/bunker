package pvp

import (
	"os"
	"path/filepath"
	"slices"
	"testing"

	"lunar-tear/server/internal/mods"
	"lunar-tear/server/internal/store"
)

func storyMods(t *testing.T, on bool) {
	t.Helper()
	mods.Recheck = 0
	path := filepath.Join(t.TempDir(), "mods.json")
	body := `{}`
	if on {
		body = `{"storyFriends": true}`
	}
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	mods.SetPath(path)
	t.Cleanup(func() { mods.SetPath("") })
}

func TestStoryFriendsOffIsUnchanged(t *testing.T) {
	c, _ := realSave(t)
	storyMods(t, false)
	season, _ := c.Season(seasonTime(c))
	l := c.Ladder(season.PvpSeasonId)
	if got, _ := l.Get(CpuIdBase + 1); got != l.cpus[0] {
		t.Fatalf("mod off: slot 1 is %+v, want %+v", got, l.cpus[0])
	}
	f := &store.FriendState{Friends: []int64{CpuIdBase + 300}}
	if ids := FriendIds(f); !slices.Equal(ids, f.Friends) {
		t.Fatalf("mod off: friends %v", ids)
	}
}

func TestStoryFriendsAreFriends(t *testing.T) {
	c, _ := realSave(t)
	storyMods(t, true)
	f := &store.FriendState{Friends: []int64{CpuIdBase + 300}}
	ids := FriendIds(f)
	if len(ids) != 1+len(StoryCharacters) || ids[0] != CpuIdBase+300 {
		t.Fatalf("friends %v", ids)
	}
	story := CpuIdBase + 1
	if !IsFriend(f, story) || !c.Cheer(f, story, 1) || !c.ReceiveCheer(f, story, 1) {
		t.Fatal("a story friend is a friend who can be cheered and cheers")
	}
	if len(f.Friends) != 1 {
		t.Fatalf("the save's friend list was written: %v", f.Friends)
	}
}

func TestStoryCPULeadsWithTheirCharacter(t *testing.T) {
	c, _ := realSave(t)
	storyMods(t, true)
	season, _ := c.Season(seasonTime(c))
	characterOf := map[int32]int32{}
	for _, p := range c.costumes {
		characterOf[p.CostumeId] = p.CharacterId
	}
	for i, ch := range StoryCharacters {
		cpu := c.StoryCPU(i, season.PvpSeasonId)
		if cpu.Name != ch.Name || cpu.PlayerId != CpuIdBase+int64(i)+1 {
			t.Fatalf("slot %d: %+v, want %s", i, cpu, ch.Name)
		}
		if characterOf[cpu.Costumes[0]] != ch.CharacterId || cpu.Weapons[0] == 0 {
			t.Fatalf("%s leads with costume %d (character %d)", ch.Name, cpu.Costumes[0], characterOf[cpu.Costumes[0]])
		}
		for _, other := range cpu.Costumes[1:] {
			if other != 0 && characterOf[other] == ch.CharacterId {
				t.Fatalf("%s twice in one deck: %v", ch.Name, cpu.Costumes)
			}
		}
	}
}

func TestStoryCPUsInTheLadder(t *testing.T) {
	c, _ := realSave(t)
	storyMods(t, true)
	season, _ := c.Season(seasonTime(c))
	l := c.Ladder(season.PvpSeasonId)
	if got, _ := l.Get(CpuIdBase + 1); got.Name != StoryCharacters[0].Name {
		t.Fatalf("Get: %+v", got)
	}
	found := false
	for _, e := range l.Ranked(1, l.Size()+1, 0) {
		if e.CPU.PlayerId == CpuIdBase+1 {
			found = e.CPU.Name == StoryCharacters[0].Name
		}
	}
	if !found {
		t.Fatal("the ranking doesn't show the story friend")
	}
}

// Story friends fill only the free places in the friend list: the save's
// friends come first, and the list never shows more than the game's limit.
func TestStoryFriendsKeepTheFriendLimit(t *testing.T) {
	storyMods(t, true)
	f := &store.FriendState{}
	for i := range 80 {
		f.Friends = append(f.Friends, CpuIdBase+300+int64(i))
	}
	ids := FriendIds(f)
	if len(ids) != 100 || !slices.Equal(ids[:80], f.Friends) {
		t.Fatalf("%d friends shown, want 100 with the save's 80 first", len(ids))
	}
	if IsFriend(f, storyIds()[len(StoryCharacters)-1]) {
		t.Fatal("a story friend past the limit counts as a friend")
	}
}
