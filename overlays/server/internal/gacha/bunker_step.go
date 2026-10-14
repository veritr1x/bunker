package gacha

import "lunar-tear/server/internal/store"

// CurrentStep is the step a multi-step summon is on: 1 when not drawn yet
// (saved step 0), or when the saved step is past the summon's last (saves
// from when summons had more steps).
func CurrentStep(entry store.GachaCatalogEntry, bs store.GachaBannerState) int32 {
	if bs.StepNumber < 1 || bs.StepNumber > entry.MaxStepNumber {
		return 1
	}
	return bs.StepNumber
}
