package runtime

import (
	"fmt"
	"log"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/mods"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// consumableItemTypeGachaMedal is Dark.Generated.Type.ConsumableItemType GACHA_MEDAL.
const consumableItemTypeGachaMedal int32 = 120

// wireGranter gives the shared PossessionGranter what it needs beyond the
// quest catalog: duplicate conversion, enhanced grants and possession limits.
func wireGranter(g *store.PossessionGranter, config *masterdata.GameConfig, costumes *masterdata.CostumeCatalog) error {
	t, err := masterdata.LoadGranterTables()
	if err != nil {
		return fmt.Errorf("load granter tables: %w", err)
	}
	g.CostumeDuplicateExchange = t.CostumeDuplicateExchange
	g.CompanionDuplicateExchange = t.CompanionDuplicateExchange
	g.CostumeEnhancedById = t.CostumeEnhanced
	g.CompanionEnhancedById = t.CompanionEnhanced
	g.CostumeExpForLevel = costumes.ExpForLevel
	g.ApplyCostumeAwaken = costumes.ApplyAwakenStep
	g.Limits = store.PossessionLimits{
		Weapon:         config.PossessionCountLimitWeapon,
		Parts:          config.PossessionCountLimitParts,
		Material:       config.PossessionCountLimitMaterial,
		ConsumableItem: config.PossessionCountLimitConsumableItem,
		Money:          config.PossessionCountLimitMoney,
		ImportantItem:  config.PossessionCountLimitImportantItem,
		GachaMedal:     config.PossessionCountLimitGachaMedal,
	}
	items, err := utils.ReadTable[masterdata.EntityMConsumableItem]("m_consumable_item")
	if err != nil {
		return fmt.Errorf("load consumable items: %w", err)
	}
	g.GachaMedalItemIds = make(map[int32]bool)
	for _, it := range items {
		if it.ConsumableItemType == consumableItemTypeGachaMedal {
			g.GachaMedalItemIds[it.ConsumableItemId] = true
		}
	}
	g.Rewrite = modRewrite(items, config.ConsumableItemIdForGold)
	log.Printf("granter: %d costume / %d companion duplicate exchanges, %d enhanced costumes, %d enhanced companions",
		len(t.CostumeDuplicateExchange), len(t.CompanionDuplicateExchange), len(t.CostumeEnhanced), len(t.CompanionEnhanced))
	return nil
}

// Pod Programs > Mods: items that arrive as something else (from the Lunar
// Tear Comfort Mod by NavHobbyDev, MIT, which uses the same values). Only items
// granted from then on change; items already held stay.
var (
	// Stamina items become gold: the gold each one is worth.
	staminaItemGold = map[int32]int32{3001: 120, 3002: 240, 3003: 360}
	// Premium tickets become gems: the free gems each premium summon ticket is
	// worth. 1203-1224, the guaranteed summon tickets, are 9,000 each. Chapter
	// tickets are not listed: they are spent on chapter summons.
	ticketGems = func() map[int32]int32 {
		m := map[int32]int32{1002: 300, 1003: 3000, 1004: 1500, 1005: 1800, 1006: 6000, 1201: 3000, 1202: 3000}
		for id := int32(1203); id <= 1224; id++ {
			m[id] = 9000
		}
		return m
	}()
)

// modRewrite is the granter's Rewrite: the conversions the mods turn on, for
// the items this master data has.
func modRewrite(items []masterdata.EntityMConsumableItem, goldItemId int32) func(model.PossessionType, int32, int32) (model.PossessionType, int32, int32) {
	exists := make(map[int32]bool, len(items))
	for _, it := range items {
		exists[it.ConsumableItemId] = true
	}
	return func(possessionType model.PossessionType, possessionId, count int32) (model.PossessionType, int32, int32) {
		if possessionType != model.PossessionTypeConsumableItem || count <= 0 || !exists[possessionId] {
			return possessionType, possessionId, count
		}
		s := mods.Get()
		if gold, ok := staminaItemGold[possessionId]; ok && s.StaminaItemsToGold && goldItemId != 0 {
			return model.PossessionTypeConsumableItem, goldItemId, count * gold
		}
		if gems, ok := ticketGems[possessionId]; ok && s.TicketsToGems {
			return model.PossessionTypeFreeGem, 0, count * gems
		}
		return possessionType, possessionId, count
	}
}
