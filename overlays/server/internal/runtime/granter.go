package runtime

import (
	"fmt"
	"log"

	"lunar-tear/server/internal/masterdata"
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
	log.Printf("granter: %d costume / %d companion duplicate exchanges, %d enhanced costumes, %d enhanced companions",
		len(t.CostumeDuplicateExchange), len(t.CompanionDuplicateExchange), len(t.CostumeEnhanced), len(t.CompanionEnhanced))
	return nil
}
