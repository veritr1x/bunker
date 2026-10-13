package userdata

// Costume tables the client reads for battle stats but the server derives:
// the character-wide costume level bonus and the karma (lottery effect)
// abilities and status ups. They follow from owned costumes and drawn
// lottery effects, so they are projected rather than stored. The file name
// sorts after zz_bunker.go so these replace the empty placeholders.

import (
	"log"
	"sort"
	"sync"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

func init() {
	register("IUserCharacterCostumeLevelBonus", func(user store.UserState) string {
		s, _ := utils.EncodeJSONMaps(characterCostumeLevelBonusRecords(user)...)
		return s
	})
	register("IUserCostumeLotteryEffectAbility", func(user store.UserState) string {
		abilities, _ := lotteryEffectRecords(user)
		s, _ := utils.EncodeJSONMaps(abilities...)
		return s
	})
	register("IUserCostumeLotteryEffectStatusUp", func(user store.UserState) string {
		_, statusUps := lotteryEffectRecords(user)
		s, _ := utils.EncodeJSONMaps(statusUps...)
		return s
	})
}

// costumeChangedTables lists the derived costume tables whose inputs changed.
func costumeChangedTables(before, after *store.UserState) []string {
	var out []string
	if !costumeLevelsEqual(before, after) {
		out = append(out, "IUserCharacterCostumeLevelBonus")
	}
	if !mapsEqualStruct(before.CostumeLotteryEffects, after.CostumeLotteryEffects) || len(before.Costumes) != len(after.Costumes) {
		out = append(out, "IUserCostumeLotteryEffectAbility", "IUserCostumeLotteryEffectStatusUp")
	}
	return out
}

func costumeDerivedKeyFields(table string) []string {
	switch table {
	case "IUserCharacterCostumeLevelBonus":
		return []string{"userId", "characterId", "statusCalculationType"}
	case "IUserCostumeLotteryEffectAbility":
		return []string{"userId", "userCostumeUuid", "slotNumber"}
	case "IUserCostumeLotteryEffectStatusUp":
		return []string{"userId", "userCostumeUuid", "statusCalculationType"}
	}
	return nil
}

// statusSum is one status row: the six stats for one StatusCalculationType.
type statusSum struct {
	hp, attack, vitality, agility, criticalRatio, criticalAttack int32
	latestVersion                                                int64
}

func (s *statusSum) add(kind model.StatusKindType, value int32) {
	switch kind {
	case model.StatusKindTypeHp:
		s.hp += value
	case model.StatusKindTypeAttack:
		s.attack += value
	case model.StatusKindTypeVitality:
		s.vitality += value
	case model.StatusKindTypeAgility:
		s.agility += value
	case model.StatusKindTypeCriticalRatio:
		s.criticalRatio += value
	case model.StatusKindTypeCriticalAttack:
		s.criticalAttack += value
	}
}

func (s statusSum) fields(row map[string]any) map[string]any {
	row["hp"] = s.hp
	row["attack"] = s.attack
	row["vitality"] = s.vitality
	row["agility"] = s.agility
	row["criticalRatio"] = s.criticalRatio
	row["criticalAttack"] = s.criticalAttack
	row["latestVersion"] = s.latestVersion
	return row
}

// costumeLevelBonusStatus maps CostumeLevelBonusType to the stat it raises
// and whether it adds (flat) or multiplies (permil).
var costumeLevelBonusStatus = map[int32]struct {
	kind model.StatusKindType
	calc model.StatusCalculationType
}{
	1:  {model.StatusKindTypeAgility, model.StatusCalculationTypeAdd},
	2:  {model.StatusKindTypeAgility, model.StatusCalculationTypeMultiply},
	3:  {model.StatusKindTypeAttack, model.StatusCalculationTypeAdd},
	4:  {model.StatusKindTypeAttack, model.StatusCalculationTypeMultiply},
	5:  {model.StatusKindTypeCriticalAttack, model.StatusCalculationTypeAdd},
	6:  {model.StatusKindTypeCriticalRatio, model.StatusCalculationTypeAdd},
	7:  {model.StatusKindTypeHp, model.StatusCalculationTypeAdd},
	8:  {model.StatusKindTypeHp, model.StatusCalculationTypeMultiply},
	9:  {model.StatusKindTypeVitality, model.StatusCalculationTypeAdd},
	10: {model.StatusKindTypeVitality, model.StatusCalculationTypeMultiply},
}

type costumeTables struct {
	characterId   map[int32]int32                                              // CostumeId -> CharacterId
	levelBonusId  map[int32]int32                                              // CostumeId -> CostumeLevelBonusId
	levelBonuses  map[int32][]masterdata.EntityMCostumeLevelBonus              // CostumeLevelBonusId -> rows
	lotteryOdds   map[[2]int32]int32                                           // [CostumeId, SlotNumber] -> odds group
	oddsRows      map[[2]int32]masterdata.EntityMCostumeLotteryEffectOddsGroup // [group, OddsNumber]
	targetAbility map[int32]masterdata.EntityMCostumeLotteryEffectTargetAbility
	targetStatus  map[int32][]masterdata.EntityMCostumeLotteryEffectTargetStatusUp
}

var costumeDerivedTables = sync.OnceValue(func() costumeTables {
	t := costumeTables{
		characterId:   map[int32]int32{},
		levelBonusId:  map[int32]int32{},
		levelBonuses:  map[int32][]masterdata.EntityMCostumeLevelBonus{},
		lotteryOdds:   map[[2]int32]int32{},
		oddsRows:      map[[2]int32]masterdata.EntityMCostumeLotteryEffectOddsGroup{},
		targetAbility: map[int32]masterdata.EntityMCostumeLotteryEffectTargetAbility{},
		targetStatus:  map[int32][]masterdata.EntityMCostumeLotteryEffectTargetStatusUp{},
	}
	logErr := func(table string, err error) {
		if err != nil {
			log.Printf("[userdata] %s: %v", table, err)
		}
	}
	costumes, err := utils.ReadTable[masterdata.EntityMCostume]("m_costume")
	logErr("m_costume", err)
	for _, c := range costumes {
		t.characterId[c.CostumeId] = c.CharacterId
		t.levelBonusId[c.CostumeId] = c.CostumeLevelBonusId
	}
	bonuses, err := utils.ReadTable[masterdata.EntityMCostumeLevelBonus]("m_costume_level_bonus")
	logErr("m_costume_level_bonus", err)
	for _, b := range bonuses {
		t.levelBonuses[b.CostumeLevelBonusId] = append(t.levelBonuses[b.CostumeLevelBonusId], b)
	}
	effects, err := utils.ReadTable[masterdata.EntityMCostumeLotteryEffect]("m_costume_lottery_effect")
	logErr("m_costume_lottery_effect", err)
	for _, e := range effects {
		t.lotteryOdds[[2]int32{e.CostumeId, e.SlotNumber}] = e.CostumeLotteryEffectOddsGroupId
	}
	odds, err := utils.ReadTable[masterdata.EntityMCostumeLotteryEffectOddsGroup]("m_costume_lottery_effect_odds_group")
	logErr("m_costume_lottery_effect_odds_group", err)
	for _, o := range odds {
		t.oddsRows[[2]int32{o.CostumeLotteryEffectOddsGroupId, o.OddsNumber}] = o
	}
	abilities, err := utils.ReadTable[masterdata.EntityMCostumeLotteryEffectTargetAbility]("m_costume_lottery_effect_target_ability")
	logErr("m_costume_lottery_effect_target_ability", err)
	for _, a := range abilities {
		t.targetAbility[a.CostumeLotteryEffectTargetAbilityId] = a
	}
	statusUps, err := utils.ReadTable[masterdata.EntityMCostumeLotteryEffectTargetStatusUp]("m_costume_lottery_effect_target_status_up")
	logErr("m_costume_lottery_effect_target_status_up", err)
	for _, s := range statusUps {
		t.targetStatus[s.CostumeLotteryEffectTargetStatusUpId] = append(t.targetStatus[s.CostumeLotteryEffectTargetStatusUpId], s)
	}
	return t
})

// characterCostumeLevelBonusRecords sums, per character and calculation type,
// every m_costume_level_bonus row each owned costume has reached at its level.
func characterCostumeLevelBonusRecords(user store.UserState) []map[string]any {
	t := costumeDerivedTables()
	// One entry per costume id: its highest level and newest change.
	level, version := map[int32]int32{}, map[int32]int64{}
	for _, c := range user.Costumes {
		level[c.CostumeId] = max(level[c.CostumeId], c.Level)
		version[c.CostumeId] = max(version[c.CostumeId], c.LatestVersion, c.AcquisitionDatetime)
	}
	type key struct {
		characterId int32
		calc        model.StatusCalculationType
	}
	sums := map[key]*statusSum{}
	for costumeId, lv := range level {
		for _, b := range t.levelBonuses[t.levelBonusId[costumeId]] {
			st, ok := costumeLevelBonusStatus[b.CostumeLevelBonusType]
			if !ok || b.Level > lv {
				continue
			}
			k := key{t.characterId[costumeId], st.calc}
			if sums[k] == nil {
				sums[k] = &statusSum{}
			}
			sums[k].add(st.kind, b.EffectValue)
			sums[k].latestVersion = max(sums[k].latestVersion, version[costumeId])
		}
	}
	keys := make([]key, 0, len(sums))
	for k := range sums {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].characterId != keys[j].characterId {
			return keys[i].characterId < keys[j].characterId
		}
		return keys[i].calc < keys[j].calc
	})
	rows := make([]map[string]any, 0, len(keys))
	for _, k := range keys {
		rows = append(rows, sums[k].fields(map[string]any{
			"userId":                user.UserId,
			"characterId":           k.characterId,
			"statusCalculationType": int32(k.calc),
		}))
	}
	return rows
}

// lotteryEffectRecords resolves each drawn karma slot through its odds group
// to an ability (one row per slot) or a status up (summed per costume and
// calculation type).
func lotteryEffectRecords(user store.UserState) (abilities, statusUps []map[string]any) {
	// Empty tables go to the client as [], never null: null stops its first load.
	abilities, statusUps = []map[string]any{}, []map[string]any{}
	t := costumeDerivedTables()
	keys := make([]store.CostumeLotteryEffectKey, 0, len(user.CostumeLotteryEffects))
	for k, e := range user.CostumeLotteryEffects {
		if e.OddsNumber != 0 {
			keys = append(keys, k)
		}
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].UserCostumeUuid != keys[j].UserCostumeUuid {
			return keys[i].UserCostumeUuid < keys[j].UserCostumeUuid
		}
		return keys[i].SlotNumber < keys[j].SlotNumber
	})
	type key struct {
		uuid string
		calc int32
	}
	sums := map[key]*statusSum{}
	var order []key
	for _, k := range keys {
		e := user.CostumeLotteryEffects[k]
		costume, ok := user.Costumes[k.UserCostumeUuid]
		if !ok {
			continue
		}
		group := t.lotteryOdds[[2]int32{costume.CostumeId, k.SlotNumber}]
		odds, ok := t.oddsRows[[2]int32{group, e.OddsNumber}]
		if !ok {
			continue
		}
		switch model.CostumeLotteryEffectType(odds.CostumeLotteryEffectType) {
		case model.CostumeLotteryEffectTypeAbility:
			a, ok := t.targetAbility[odds.CostumeLotteryEffectTargetId]
			if !ok {
				continue
			}
			abilities = append(abilities, map[string]any{
				"userId":          user.UserId,
				"userCostumeUuid": k.UserCostumeUuid,
				"slotNumber":      k.SlotNumber,
				"abilityId":       a.AbilityId,
				"abilityLevel":    a.AbilityLevel,
				"latestVersion":   e.LatestVersion,
			})
		case model.CostumeLotteryEffectTypeStatusUp:
			for _, s := range t.targetStatus[odds.CostumeLotteryEffectTargetId] {
				sk := key{k.UserCostumeUuid, s.StatusCalculationType}
				if sums[sk] == nil {
					sums[sk] = &statusSum{}
					order = append(order, sk)
				}
				sums[sk].add(model.StatusKindType(s.StatusKindType), s.EffectValue)
				sums[sk].latestVersion = max(sums[sk].latestVersion, e.LatestVersion)
			}
		}
	}
	sort.Slice(order, func(i, j int) bool {
		if order[i].uuid != order[j].uuid {
			return order[i].uuid < order[j].uuid
		}
		return order[i].calc < order[j].calc
	})
	for _, sk := range order {
		statusUps = append(statusUps, sums[sk].fields(map[string]any{
			"userId":                user.UserId,
			"userCostumeUuid":       sk.uuid,
			"statusCalculationType": sk.calc,
		}))
	}
	return abilities, statusUps
}
