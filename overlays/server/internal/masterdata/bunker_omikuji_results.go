package masterdata

import "math/rand/v2"

// omikujiFortunes is how many fortunes each draw's art set has. The game
// data only names the set (m_omikuji's asset id, e.g. 100); the result
// screens are omikuji_result_<set+1> to <set+n> in the game files, and the
// client shows the one the server returns.
var omikujiFortunes = map[int32]int32{
	100: 5, 200: 17, 300: 5, 400: 21, 500: 21, 600: 5, 700: 22,
}

// DrawFortune picks one of the draw's fortunes at random, as the result
// screen id to show. A set with no known fortunes returns its own id.
func (c *OmikujiCatalog) DrawFortune(omikujiId int32) int32 {
	set := c.LookupAssetId(omikujiId)
	n := omikujiFortunes[set]
	if n == 0 {
		return set
	}
	return set + 1 + rand.Int32N(n)
}
