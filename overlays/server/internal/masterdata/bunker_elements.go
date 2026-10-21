package masterdata

import (
	"log"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/utils"
)

// Elements of the items summons give: a weapon's from m_weapon, a costume's
// from its paired weapon (the game shows a character in its weapon's element).
var (
	weaponElement  = map[int32]int32{}
	costumeElement = map[int32]int32{}
)

// elementNames are m_weapon's AttributeType values.
var elementNames = map[string]int32{"dark": 1, "fire": 2, "light": 3, "water": 5, "wind": 6}

// ElementByName is the AttributeType of "fire", "water", ...
func ElementByName(name string) (int32, bool) {
	e, ok := elementNames[name]
	return e, ok
}

// ElementOf is the element of a costume or weapon (0 if unknown).
func ElementOf(it GachaPoolItem) int32 {
	if it.PossessionType == int32(model.PossessionTypeCostume) {
		return costumeElement[it.PossessionId]
	}
	return weaponElement[it.PossessionId]
}

// SetElementsForTest replaces the element tables.
func SetElementsForTest(weapons, costumes map[int32]int32) {
	weaponElement, costumeElement = weapons, costumes
	if weaponElement == nil {
		weaponElement = map[int32]int32{}
	}
	if costumeElement == nil {
		costumeElement = map[int32]int32{}
	}
}

func (pool *GachaCatalog) loadElements() {
	rows, err := utils.ReadTable[EntityMWeapon]("m_weapon")
	if err != nil {
		log.Printf("summon rules: weapon elements: %v", err)
		return
	}
	weapons := make(map[int32]int32, len(rows))
	for _, w := range rows {
		weapons[w.WeaponId] = w.AttributeType
	}
	costumes := make(map[int32]int32, len(pool.CostumeWeaponMap))
	for c, w := range pool.CostumeWeaponMap {
		if e, ok := weapons[w]; ok {
			costumes[c] = e
		}
	}
	SetElementsForTest(weapons, costumes)
}
