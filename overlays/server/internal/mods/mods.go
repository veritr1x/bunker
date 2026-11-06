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
}

// MaxRewardMultiplier is the largest reward multiplier.
const MaxRewardMultiplier = 10

// Validate reports a setting out of range.
func (s Settings) Validate() error {
	if s.RewardMultiplier < 0 || s.RewardMultiplier > MaxRewardMultiplier {
		return fmt.Errorf("the reward multiplier must be 1–%d", MaxRewardMultiplier)
	}
	return nil
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
