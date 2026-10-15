package campaign

// Glorious Success Rate Up campaigns. For characters and weapons, an enhance
// campaign raises the chance of a glorious (great) success, not the
// experience: the game's text names them "Glorious success character-enhance
// rate up" and "Glorious success weapon-enhance rate up". The client works out
// a campaign's rate the same way as for memoirs (GetEnhanceCampaignRate):
// PROBABILITY_PER_MILE sets it to value/10 ‰, ADDITIONAL_PER_MILE adds value/10 ‰.

func (c *Catalog) CostumeGreatSuccessBonus(t CostumeTarget, f Filter) RateBonus {
	var out RateBonus
	for _, r := range c.enhance {
		if r.isActive(f) && matchesCostume(r.targets, t) {
			out = applyEnhanceEffect(out, r)
		}
	}
	return out
}

func (c *Catalog) WeaponGreatSuccessBonus(t WeaponTarget, f Filter) RateBonus {
	var out RateBonus
	for _, r := range c.enhance {
		if r.isActive(f) && matchesWeapon(r.targets, t) {
			out = applyEnhanceEffect(out, r)
		}
	}
	return out
}
