package service

// bannerSeen keeps one summon per banner in the summon list. A rerun Bunker
// added (summon_rules.json "new") runs on the calendar with its own dates, a
// summon of its own beside the first run; with the calendar off every run is
// open at once and the list showed the banner two or three times. The first
// open summon with a banner is listed: the game data's, then the added ones
// in their order.
type bannerSeen map[string]bool

// first is true for the first summon with this banner name; unnamed ones always.
func (seen bannerSeen) first(name string) bool {
	if name == "" {
		return true
	}
	if seen[name] {
		return false
	}
	seen[name] = true
	return true
}
