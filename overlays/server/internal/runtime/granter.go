package runtime

import (
	"fmt"
	"log"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

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
	}
	log.Printf("granter: %d costume / %d companion duplicate exchanges, %d enhanced costumes, %d enhanced companions",
		len(t.CostumeDuplicateExchange), len(t.CompanionDuplicateExchange), len(t.CostumeEnhanced), len(t.CompanionEnhanced))
	return nil
}
