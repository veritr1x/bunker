// Package mods holds the gameplay changes the player can turn on in Pod
// Programs > Mods. Bunker otherwise plays like the original game: every mod is
// off unless mods.json in the save folder turns it on. The server reads the
// file again only when it changes, so a mod takes effect on the next call
// that uses it, with no restart.
//
// Most mods come from the Lunar Tear Comfort Mod by NavHobbyDev (MIT):
// https://github.com/NavHobbyDev/lunar-tear-comfort-mod
//
// A mod changes what the server does from then on; it never rewrites a save
// on its own, so turning one off leaves the save as the mod left it.
package mods

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"sync"
	"time"
)

// Settings are the mods in use. The zero value is the original game.
type Settings struct {
	// StaminaFree: quests, skips and other content cost no stamina.
	StaminaFree bool `json:"staminaFree"`
	// StaminaItemsToGold: stamina recovery items are granted as gold instead.
	StaminaItemsToGold bool `json:"staminaItemsToGold"`
	// TicketsToGems: premium summon tickets are granted as free gems instead.
	TicketsToGems bool `json:"ticketsToGems"`
	// ShopUnlimited: shop items that restock daily, weekly or monthly never
	// run out; items with a lifetime limit keep it.
	ShopUnlimited bool `json:"shopUnlimited"`
	// LostItemGems: picking up a Lost Item gives a random amount of free gems.
	LostItemGems bool `json:"lostItemGems"`
	// RewardMultiplier multiplies a quest's drops, gold and gems (1 = off).
	RewardMultiplier int32 `json:"rewardMultiplier"`
	// NoDuplicateFourStar: a ★4 costume or weapon you already own is swapped
	// for one you don't from the same summon, until you own them all.
	NoDuplicateFourStar bool `json:"noDuplicateFourStar"`
	// PityRewards: every 100 summon medals become 1,000 paid gems and 100
	// Mama Points, sent to the gift box.
	PityRewards bool `json:"pityRewards"`
	// UnlimitedDailyPlays: quests with a daily clear limit don't count their
	// clears, so they can be played as often as you like.
	UnlimitedDailyPlays bool `json:"unlimitedDailyPlays"`
	// FreeSkips: skipping a quest uses no skip tickets.
	FreeSkips bool `json:"freeSkips"`
	// ExpMultiplier multiplies the EXP a quest gives you, your characters and
	// their costumes (1 = off).
	ExpMultiplier int32 `json:"expMultiplier"`
	// StoryFriends: characters from the story join your friends and the Arena.
	StoryFriends bool `json:"storyFriends"`

	// Challenges change the game data (Pod Programs applies them); the server
	// reads them for the challenge bonus.

	// HardEnemies multiplies every enemy's stats: 0 or 1 is off, else 1.5, 2,
	// 3 or 5.
	HardEnemies float64 `json:"hardEnemies"`
	// WeaknessOnly: hits that aren't super-effective do half damage.
	WeaknessOnly bool `json:"weaknessOnly"`
	// SlowSkills: your skills take 50% longer to come back.
	SlowSkills bool `json:"slowSkills"`
}

// hardEnemiesBonus is each Hard enemies setting's reward bonus.
var hardEnemiesBonus = map[float64]int32{1.5: 2, 2: 3, 3: 4, 5: 6}

// MaxChallengeBonus caps the challenge bonus, as the reward multiplier is.
const MaxChallengeBonus = MaxRewardMultiplier

// MaxRewardMultiplier is the largest reward multiplier.
const MaxRewardMultiplier = 10

// Validate reports a setting out of range.
func (s Settings) Validate() error {
	if s.RewardMultiplier < 0 || s.RewardMultiplier > MaxRewardMultiplier {
		return fmt.Errorf("the reward multiplier must be 1–%d", MaxRewardMultiplier)
	}
	if s.ExpMultiplier < 0 || s.ExpMultiplier > MaxRewardMultiplier {
		return fmt.Errorf("the EXP multiplier must be 1–%d", MaxRewardMultiplier)
	}
	if _, ok := hardEnemiesBonus[s.HardEnemies]; !ok && s.HardEnemies != 0 && s.HardEnemies != 1 {
		return fmt.Errorf("hard enemies must be 1.5, 2, 3 or 5")
	}
	return nil
}

// ExpFactor is the EXP multiplier, at least 1.
func (s Settings) ExpFactor() int32 {
	if s.ExpMultiplier < 1 {
		return 1
	}
	return s.ExpMultiplier
}

// Comfort reports whether any Quests, Items & shops or Summons mod is on.
// World mods and challenges don't count.
func (s Settings) Comfort() bool {
	return s.StaminaFree || s.StaminaItemsToGold || s.TicketsToGems || s.ShopUnlimited || s.LostItemGems ||
		s.Multiplier() > 1 || s.NoDuplicateFourStar || s.PityRewards ||
		s.UnlimitedDailyPlays || s.FreeSkips || s.ExpFactor() > 1
}

// ChallengeBonus multiplies quest rewards for the challenges that are on,
// capped at MaxChallengeBonus. It is 1 while a comfort mod is on, and on a
// game day when Start a new day was pressed (pausedToday).
func (s Settings) ChallengeBonus(pausedToday bool) int32 {
	if pausedToday || s.Comfort() {
		return 1
	}
	bonus := int32(1)
	if b, ok := hardEnemiesBonus[s.HardEnemies]; ok {
		bonus *= b
	}
	if s.WeaknessOnly {
		bonus *= 2
	}
	if s.SlowSkills {
		bonus *= 2
	}
	return min(bonus, MaxChallengeBonus)
}

// RewardFactor multiplies a quest's drops, gold and gems: the reward
// multiplier while comfort mods are on, else the challenge bonus.
func (s Settings) RewardFactor(pausedToday bool) int32 {
	if s.Comfort() {
		return s.Multiplier()
	}
	return s.ChallengeBonus(pausedToday)
}

// Multiplier is the reward multiplier, at least 1.
func (s Settings) Multiplier() int32 {
	if s.RewardMultiplier < 1 {
		return 1
	}
	return s.RewardMultiplier
}

var current struct {
	sync.Mutex
	path    string
	modTime time.Time
	size    int64
	s       Settings
	checked time.Time // when the file was last looked at
}

// Recheck is how often Get looks at the file again. Get is called for every
// item granted and every stamina cost, so it does not touch the file on each
// call; a change in Pod Programs is in use within this time. Tests set 0.
var Recheck = time.Second

// SetPath names the settings file (mods.json in the save folder); "" turns
// every mod off.
func SetPath(path string) {
	current.Lock()
	current.path, current.modTime, current.size, current.s, current.checked = path, time.Time{}, -1, Settings{}, time.Time{}
	current.Unlock()
}

// Get returns the mods in use: none without the file, or with an invalid one.
func Get() Settings {
	current.Lock()
	defer current.Unlock()
	if current.path == "" {
		return Settings{}
	}
	now := time.Now()
	if !current.checked.IsZero() && now.Sub(current.checked) < Recheck {
		return current.s
	}
	current.checked = now
	info, err := os.Stat(current.path)
	if err != nil {
		current.modTime, current.size, current.s = time.Time{}, -1, Settings{}
		return Settings{}
	}
	if info.ModTime().Equal(current.modTime) && info.Size() == current.size {
		return current.s
	}
	current.modTime, current.size, current.s = info.ModTime(), info.Size(), Settings{}
	data, err := os.ReadFile(current.path)
	if err != nil {
		return Settings{}
	}
	var s Settings
	if err := json.Unmarshal(data, &s); err != nil {
		log.Printf("[mods] %s: %v; no mods", current.path, err)
		return Settings{}
	}
	if err := s.Validate(); err != nil {
		log.Printf("[mods] %s: %v; no mods", current.path, err)
		return Settings{}
	}
	current.s = s
	log.Printf("[mods] in use: %+v", s)
	return s
}
