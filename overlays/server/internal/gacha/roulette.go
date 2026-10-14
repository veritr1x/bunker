package gacha

// The Special Gift Roulette (Global only): after a video ad the menu's wheel
// pays free gems, up to REWARD_GACHA_DAILY_MAX_COUNT spins a day. The wheel
// shows 15 slices (six 10s, four 30s, two 50s, two 100s, one 3000), but the
// result was a weighted draw: the rates were never published, and players saw
// mostly 10s, a 100 now and then and the 3000 very rarely. The client only
// animates these five amounts.
//
// Pod Programs > Summon rates can change the chances: it writes
// roulette_rates.json next to the save, read again whenever it changes.

import (
	"encoding/json"
	"fmt"
	"log"
	"math"
	"os"
	"sync"
	"time"
)

// RouletteGems are the wheel's amounts, in the order of RouletteRates.Percents.
var RouletteGems = [5]int32{10, 30, 50, 100, 3000}

// RouletteRates are the chances of each amount, in percent.
type RouletteRates struct {
	Percents [5]float64 `json:"percents"`
}

// DefaultRouletteRates: 10 60%, 30 25%, 50 10%, 100 4.7%, 3000 0.3%.
var DefaultRouletteRates = RouletteRates{Percents: [5]float64{60, 25, 10, 4.7, 0.3}}

func (r RouletteRates) Validate() error {
	total := 0.0
	for _, p := range r.Percents {
		if p < 0 || p > 100 {
			return fmt.Errorf("each chance must be 0–100%%")
		}
		total += p
	}
	if math.Abs(total-100) > 0.001 {
		return fmt.Errorf("the chances must add up to 100%% (they add up to %.3f%%)", total)
	}
	return nil
}

var roulette struct {
	sync.Mutex
	path    string
	modTime time.Time
	rates   RouletteRates
}

// SetRouletteRatesPath names the settings file (roulette_rates.json in the save folder).
func SetRouletteRatesPath(path string) {
	roulette.Lock()
	roulette.path, roulette.modTime, roulette.rates = path, time.Time{}, DefaultRouletteRates
	roulette.Unlock()
}

// CurrentRouletteRates are the roulette chances in force.
func CurrentRouletteRates() RouletteRates {
	roulette.Lock()
	defer roulette.Unlock()
	if roulette.path == "" {
		return DefaultRouletteRates
	}
	info, err := os.Stat(roulette.path)
	if err != nil {
		roulette.modTime, roulette.rates = time.Time{}, DefaultRouletteRates
		return DefaultRouletteRates
	}
	if info.ModTime().Equal(roulette.modTime) {
		return roulette.rates
	}
	roulette.modTime, roulette.rates = info.ModTime(), DefaultRouletteRates
	data, err := os.ReadFile(roulette.path)
	if err != nil {
		return DefaultRouletteRates
	}
	var r RouletteRates
	if err = json.Unmarshal(data, &r); err == nil {
		err = r.Validate()
	}
	if err != nil {
		log.Printf("[gacha] %s: %v; using the default roulette rates", roulette.path, err)
		return DefaultRouletteRates
	}
	roulette.rates = r
	log.Printf("[gacha] roulette rates: %v%%", r.Percents)
	return r
}

// DrawRoulette picks the gems of one spin with rates; intn is rand.Intn.
func DrawRoulette(rates RouletteRates, intn func(n int) int) int32 {
	const scale = 1000 // weights in thousandths of a percent
	weights, total := [5]int{}, 0
	for i, p := range rates.Percents {
		weights[i] = int(math.Round(p * scale))
		total += weights[i]
	}
	if total <= 0 {
		return RouletteGems[0]
	}
	roll := intn(total)
	for i, w := range weights {
		if roll < w {
			return RouletteGems[i]
		}
		roll -= w
	}
	return RouletteGems[0]
}
