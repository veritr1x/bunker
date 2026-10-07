package gacha

// Summon rates the player can change in Pod Programs > Summon rates. The page
// writes gacha_rates.json next to the save; each premium draw reads it (again
// only when the file changed). Without the file, or with an invalid one, the
// rates are Lunar Tear's: 4★ 5% (2% costume, 3% weapon), 3★ 15% (5% costume,
// 10% weapon), 2★ 80%.

import (
	"encoding/json"
	"fmt"
	"log"
	"math"
	"os"
	"sync"
	"time"

	"lunar-tear/server/internal/model"
)

type RateConfig struct {
	FourStarPercent   float64 `json:"fourStarPercent"`       // 4★ share of all draws
	ThreeStarPercent  float64 `json:"threeStarPercent"`      // 3★ share; 2★ gets the rest
	FourCostumeShare  float64 `json:"fourStarCostumeShare"`  // costumes' share of 4★ (the rest are weapons)
	ThreeCostumeShare float64 `json:"threeStarCostumeShare"` // costumes' share of 3★
	FeaturedPercent   float64 `json:"featuredPercent"`       // chance a draw of a featured type and rarity is a featured item
	StepUpBoost       bool    `json:"stepUpBoost"`           // step-up banners raise 4★ on steps 1, 3 and 5
	MultiMinRarity    int32   `json:"multiMinRarity"`        // the guaranteed slot of a 10-draw: 3 or 4 (★)
}

// DefaultRates are Lunar Tear's own.
var DefaultRates = RateConfig{FourStarPercent: 5, ThreeStarPercent: 15, FourCostumeShare: 40, ThreeCostumeShare: 100.0 / 3,
	FeaturedPercent: 35, StepUpBoost: true, MultiMinRarity: 3}

func (c RateConfig) Validate() error {
	switch {
	case c.FourStarPercent < 0.1 || c.FourStarPercent > 100:
		return fmt.Errorf("4★ rate must be 0.1–100%%")
	case c.ThreeStarPercent < 0 || c.FourStarPercent+c.ThreeStarPercent > 100:
		return fmt.Errorf("4★ and 3★ together must be at most 100%%")
	case c.FourCostumeShare < 0 || c.FourCostumeShare > 100 || c.ThreeCostumeShare < 0 || c.ThreeCostumeShare > 100:
		return fmt.Errorf("costume shares must be 0–100%%")
	case c.FeaturedPercent < 0 || c.FeaturedPercent > 100:
		return fmt.Errorf("featured share must be 0–100%%")
	case c.MultiMinRarity != 3 && c.MultiMinRarity != 4:
		return fmt.Errorf("the 10-draw guarantee must be 3★ or 4★")
	}
	return nil
}

// Tiers are the draw weights out of 100000.
func (c RateConfig) Tiers() []RateTier {
	w := func(percent float64) int { return int(math.Round(percent * 1000)) }
	four, three := c.FourStarPercent, c.ThreeStarPercent
	fs, ts := c.FourCostumeShare/100, c.ThreeCostumeShare/100
	tiers := []RateTier{
		{w(four * fs), int32(model.PossessionTypeCostume), model.RaritySSRare},
		{w(four * (1 - fs)), int32(model.PossessionTypeWeapon), model.RaritySSRare},
		{w(three * ts), int32(model.PossessionTypeCostume), model.RaritySRare},
		{w(three * (1 - ts)), int32(model.PossessionTypeWeapon), model.RaritySRare},
		{w(100 - four - three), int32(model.PossessionTypeWeapon), model.RarityRare},
	}
	out := tiers[:0]
	for _, t := range tiers {
		if t.Weight > 0 {
			out = append(out, t)
		}
	}
	return out
}

// GuaranteedRarity is the rarity type the 10-draw's guaranteed slot needs.
func (c RateConfig) GuaranteedRarity() model.RarityType {
	if c.MultiMinRarity == 4 {
		return model.RaritySSRare
	}
	return model.RaritySRare
}

var rates struct {
	sync.Mutex
	path    string
	modTime time.Time
	cfg     RateConfig
}

// SetRatesPath names the settings file (gacha_rates.json in the save folder).
func SetRatesPath(path string) {
	rates.Lock()
	rates.path, rates.modTime, rates.cfg = path, time.Time{}, DefaultRates
	rates.Unlock()
}

// Rates are the summon rates in force.
func Rates() RateConfig {
	rates.Lock()
	defer rates.Unlock()
	if rates.path == "" {
		return DefaultRates
	}
	info, err := os.Stat(rates.path)
	if err != nil {
		rates.modTime, rates.cfg = time.Time{}, DefaultRates
		return DefaultRates
	}
	if info.ModTime().Equal(rates.modTime) {
		return rates.cfg
	}
	rates.modTime, rates.cfg = info.ModTime(), DefaultRates
	data, err := os.ReadFile(rates.path)
	if err != nil {
		return DefaultRates
	}
	cfg := DefaultRates
	if err := json.Unmarshal(data, &cfg); err != nil {
		log.Printf("[gacha] %s: %v; using the default rates", rates.path, err)
		return DefaultRates
	}
	if err := cfg.Validate(); err != nil {
		log.Printf("[gacha] %s: %v; using the default rates", rates.path, err)
		return DefaultRates
	}
	rates.cfg = cfg
	log.Printf("[gacha] summon rates: 4★ %.2f%% (%.0f%% costumes) 3★ %.2f%% (%.0f%% costumes) featured %.0f%% step-up %v 10-draw %d★",
		cfg.FourStarPercent, cfg.FourCostumeShare, cfg.ThreeStarPercent, cfg.ThreeCostumeShare, cfg.FeaturedPercent, cfg.StepUpBoost, cfg.MultiMinRarity)
	return cfg
}
