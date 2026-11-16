package lunarbase

import (
	"errors"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Bunker: Pod Programs › Item Editor › Set (android_items.py).
// "set_possession_batch" makes each listed stackable's count the amount given
// ("grants", as grant_batch, a count of 0 or more): materials, consumables,
// important items and gems, up or down. The whole batch is checked before
// anything is written.

const maxStack = 2147483647

func runSetPossessionBatch(req *request) (int, error) {
	if len(req.Grants) == 0 {
		return 0, errors.New("grants list is empty")
	}
	for _, g := range req.Grants {
		if g.Count < 0 {
			return 0, errors.New("count must not be negative")
		}
		switch model.PossessionType(g.PossessionType) {
		case model.PossessionTypeMaterial, model.PossessionTypeConsumableItem, model.PossessionTypePaidGem,
			model.PossessionTypeFreeGem, model.PossessionTypeImportantItem:
		default:
			return 0, errors.New("unsupported stackable item type")
		}
	}
	db, st, err := openDB(req.DBPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	user, err := st.LoadUser(req.UserID)
	if err != nil {
		return 0, err
	}
	// Paid and free gems are spent as one balance, which must stay a 32-bit count.
	paid, free := int64(user.Gem.PaidGem), int64(user.Gem.FreeGem)
	for _, g := range req.Grants {
		switch model.PossessionType(g.PossessionType) {
		case model.PossessionTypePaidGem:
			paid = int64(g.Count)
		case model.PossessionTypeFreeGem:
			free = int64(g.Count)
		}
	}
	if paid+free > maxStack {
		return 0, errors.New("set would exceed the game's inventory limit")
	}
	if _, err := st.UpdateUser(req.UserID, func(u *store.UserState) {
		for _, g := range req.Grants {
			switch model.PossessionType(g.PossessionType) {
			case model.PossessionTypeMaterial:
				u.Materials[g.PossessionID] = g.Count
			case model.PossessionTypeConsumableItem:
				u.ConsumableItems[g.PossessionID] = g.Count
			case model.PossessionTypePaidGem:
				u.Gem.PaidGem = g.Count
			case model.PossessionTypeFreeGem:
				u.Gem.FreeGem = g.Count
			case model.PossessionTypeImportantItem:
				u.ImportantItems[g.PossessionID] = g.Count
			}
		}
	}); err != nil {
		return 0, err
	}
	return len(req.Grants), nil
}
