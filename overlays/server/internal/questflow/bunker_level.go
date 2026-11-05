package questflow

import "lunar-tear/server/internal/gameutil"

// playerLevel is the player level and exp after exp is added. The level comes
// from the total exp (gameutil.LevelAndCap) but never goes below the level the
// player had: a save edited to a level without the exp for it would otherwise
// fall back to level 1 on its next exp.
func playerLevel(oldLevel, exp int32, thresholds []int32) (level, capped int32) {
	level, capped = gameutil.LevelAndCap(exp, thresholds)
	return max(level, oldLevel), capped
}
