package service

import "math/rand"

// Great success. Costume and weapon enhancements could end in a "great
// success" (the client has its own animation and the response flag), which
// gave more experience. Its chance and size are not in the game data, so
// these are chosen here: 10% of enhancements, half again the experience.
const (
	greatSuccessPercent = 10
	greatSuccessPermil  = 1500
)

// rollGreatSuccess decides one enhancement; intn is rand.Intn.
func rollGreatSuccess(exp int32, intn func(int) int) (int32, bool) {
	if exp <= 0 || intn(100) >= greatSuccessPercent {
		return exp, false
	}
	return int32(int64(exp) * greatSuccessPermil / 1000), true
}

var greatSuccessRand = rand.Intn
