package userdata

// The Original calendar replays an Abyss Tower's runs as copies of its chapter
// (the chapter + n * 10,000,000); a tower's claimed rewards are one record,
// shown under each copy so every run shows what was claimed.
const (
	towerRunStep = 10_000_000
	towerMaxRuns = 10
)

func towerRunIds(base int32) []int32 {
	ids := make([]int32, 0, towerMaxRuns)
	for n := int32(0); n < towerMaxRuns; n++ {
		ids = append(ids, base+n*towerRunStep)
	}
	return ids
}
