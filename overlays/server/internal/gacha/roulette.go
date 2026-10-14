package gacha

// The Special Gift Roulette (Global only): after a video ad the menu's wheel
// pays free gems, up to REWARD_GACHA_DAILY_MAX_COUNT spins a day. The wheel
// shows 15 slices (six 10s, four 30s, two 50s, two 100s, one 3000), but the
// result was a weighted draw: the rates were never published, and players saw
// mostly 10s, a 100 now and then and the 3000 very rarely. The client only
// animates these five amounts.

// RouletteOutcome is one wheel amount and its weight in a thousand.
type RouletteOutcome struct {
	Gems   int32
	Weight int
}

var RouletteOutcomes = []RouletteOutcome{
	{Gems: 10, Weight: 600},
	{Gems: 30, Weight: 250},
	{Gems: 50, Weight: 100},
	{Gems: 100, Weight: 47},
	{Gems: 3000, Weight: 3},
}

// DrawRoulette picks the gems of one spin; intn is rand.Intn.
func DrawRoulette(intn func(n int) int) int32 {
	total := 0
	for _, o := range RouletteOutcomes {
		total += o.Weight
	}
	roll := intn(total)
	for _, o := range RouletteOutcomes {
		if roll < o.Weight {
			return o.Gems
		}
		roll -= o.Weight
	}
	return RouletteOutcomes[0].Gems
}
