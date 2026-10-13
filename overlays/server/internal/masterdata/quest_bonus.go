package masterdata

import (
	"fmt"
	"sort"

	"lunar-tear/server/internal/utils"
)

// QuestBonusType values (m_quest_bonus_effect_group.QuestBonusType).
const (
	QuestBonusTypeAbility    int32 = 1
	QuestBonusTypeExp        int32 = 2
	QuestBonusTypeDropReward int32 = 3
)

// QuestBonusCatalog holds m_quest_bonus*: a quest's QuestBonusId names the
// characters, costumes (by limit break) and weapons (by limit break) that add
// effects when they are in the deck. The client draws the extra drops on the
// result screen itself (CalculatorQuestBonus.CreateItemBonusResultDropCellData,
// from the latest selected deck); the server grants them.
type QuestBonusCatalog struct {
	BonusById            map[int32]EntityMQuestBonus
	CharacterGroups      map[int32][]EntityMQuestBonusCharacterGroup
	CostumeSettingGroups map[int32][]EntityMQuestBonusCostumeSettingGroup
	WeaponGroups         map[int32][]EntityMQuestBonusWeaponGroup
	EffectGroups         map[int32][]EntityMQuestBonusEffectGroup
	DropRewardsByEffect  map[int32][]EntityMQuestBonusDropReward
	TermsByGroup         map[int32][]EntityMQuestBonusTermGroup
}

func LoadQuestBonusCatalog() (*QuestBonusCatalog, error) {
	bonuses, err := utils.ReadTable[EntityMQuestBonus]("m_quest_bonus")
	if err != nil {
		return nil, fmt.Errorf("load quest bonus table: %w", err)
	}
	characters, err := utils.ReadTable[EntityMQuestBonusCharacterGroup]("m_quest_bonus_character_group")
	if err != nil {
		return nil, fmt.Errorf("load quest bonus character group table: %w", err)
	}
	costumes, err := utils.ReadTable[EntityMQuestBonusCostumeSettingGroup]("m_quest_bonus_costume_setting_group")
	if err != nil {
		return nil, fmt.Errorf("load quest bonus costume setting group table: %w", err)
	}
	weapons, err := utils.ReadTable[EntityMQuestBonusWeaponGroup]("m_quest_bonus_weapon_group")
	if err != nil {
		return nil, fmt.Errorf("load quest bonus weapon group table: %w", err)
	}
	effects, err := utils.ReadTable[EntityMQuestBonusEffectGroup]("m_quest_bonus_effect_group")
	if err != nil {
		return nil, fmt.Errorf("load quest bonus effect group table: %w", err)
	}
	drops, err := utils.ReadTable[EntityMQuestBonusDropReward]("m_quest_bonus_drop_reward")
	if err != nil {
		return nil, fmt.Errorf("load quest bonus drop reward table: %w", err)
	}
	terms, err := utils.ReadTable[EntityMQuestBonusTermGroup]("m_quest_bonus_term_group")
	if err != nil {
		return nil, fmt.Errorf("load quest bonus term group table: %w", err)
	}

	c := &QuestBonusCatalog{
		BonusById:            make(map[int32]EntityMQuestBonus, len(bonuses)),
		CharacterGroups:      make(map[int32][]EntityMQuestBonusCharacterGroup),
		CostumeSettingGroups: make(map[int32][]EntityMQuestBonusCostumeSettingGroup),
		WeaponGroups:         make(map[int32][]EntityMQuestBonusWeaponGroup),
		EffectGroups:         make(map[int32][]EntityMQuestBonusEffectGroup),
		DropRewardsByEffect:  make(map[int32][]EntityMQuestBonusDropReward),
		TermsByGroup:         make(map[int32][]EntityMQuestBonusTermGroup),
	}
	for _, b := range bonuses {
		c.BonusById[b.QuestBonusId] = b
	}
	for _, r := range characters {
		c.CharacterGroups[r.QuestBonusCharacterGroupId] = append(c.CharacterGroups[r.QuestBonusCharacterGroupId], r)
	}
	for _, r := range costumes {
		c.CostumeSettingGroups[r.QuestBonusCostumeSettingGroupId] = append(c.CostumeSettingGroups[r.QuestBonusCostumeSettingGroupId], r)
	}
	for _, r := range weapons {
		c.WeaponGroups[r.QuestBonusWeaponGroupId] = append(c.WeaponGroups[r.QuestBonusWeaponGroupId], r)
	}
	for _, r := range effects {
		c.EffectGroups[r.QuestBonusEffectGroupId] = append(c.EffectGroups[r.QuestBonusEffectGroupId], r)
	}
	for id := range c.EffectGroups {
		rows := c.EffectGroups[id]
		sort.Slice(rows, func(i, j int) bool { return rows[i].SortOrder < rows[j].SortOrder })
	}
	for _, r := range drops {
		c.DropRewardsByEffect[r.QuestBonusEffectId] = append(c.DropRewardsByEffect[r.QuestBonusEffectId], r)
	}
	for _, r := range terms {
		c.TermsByGroup[r.QuestBonusTermGroupId] = append(c.TermsByGroup[r.QuestBonusTermGroupId], r)
	}
	return c, nil
}

// InTerm reports whether a bonus row with this term group applies now; term
// group 0 is always on.
func (c *QuestBonusCatalog) InTerm(termGroupId int32, nowMillis int64) bool {
	if termGroupId == 0 {
		return true
	}
	for _, t := range c.TermsByGroup[termGroupId] {
		if nowMillis >= t.StartDatetime && nowMillis <= t.EndDatetime {
			return true
		}
	}
	return false
}

// DropRewards lists the DROP_REWARD effects of an effect group.
func (c *QuestBonusCatalog) DropRewards(effectGroupId int32) []EntityMQuestBonusDropReward {
	var out []EntityMQuestBonusDropReward
	for _, e := range c.EffectGroups[effectGroupId] {
		if e.QuestBonusType != QuestBonusTypeDropReward {
			continue
		}
		out = append(out, c.DropRewardsByEffect[e.QuestBonusEffectId]...)
	}
	return out
}

// ImportantItemEffectType values (m_important_item_effect.ImportantItemEffectType;
// the target id points into the table of that type).
const (
	ImportantItemEffectTypeUnlockFunction int32 = 1
	ImportantItemEffectTypeDropRate       int32 = 2
	ImportantItemEffectTypeDropCount      int32 = 3
)

// ImportantItemTargetQuestGroupType values
// (ImportantItemEffectTargetQuestGroupType in the client).
const (
	ImportantItemTargetWholeQuest              int32 = 1
	ImportantItemTargetQuestType               int32 = 2
	ImportantItemTargetEventQuestType          int32 = 3
	ImportantItemTargetMainQuestChapterId      int32 = 4
	ImportantItemTargetMainQuestQuestId        int32 = 5
	ImportantItemTargetSubQuestChapterId       int32 = 6
	ImportantItemTargetSubQuestQuestId         int32 = 7
	ImportantItemTargetMainQuestDifficultyType int32 = 8
)

// ImportantItemDropCount is a DROP_COUNT effect an owned important item gives.
type ImportantItemDropCount struct {
	ImportantItemId int32
	GroupingId      int32
	Priority        int32
	StartDatetime   int64
	EndDatetime     int64
	CountPermil     int32
	QuestGroupId    int32
	ItemGroupId     int32 // 0: every drop
}

// ImportantItemEffectCatalog holds m_important_item_effect* for the drop
// effects of owned important items ("gohobi" items).
type ImportantItemEffectCatalog struct {
	DropCounts          []ImportantItemDropCount
	QuestGroups         map[int32][]EntityMImportantItemEffectTargetQuestGroup
	ItemGroups          map[int32][]EntityMImportantItemEffectTargetItemGroup
	MainQuestDifficulty map[int32]int32 // main QuestId -> DifficultyType
}

func LoadImportantItemEffectCatalog() (*ImportantItemEffectCatalog, error) {
	items, err := utils.ReadTable[EntityMImportantItem]("m_important_item")
	if err != nil {
		return nil, fmt.Errorf("load important item table: %w", err)
	}
	effects, err := utils.ReadTable[EntityMImportantItemEffect]("m_important_item_effect")
	if err != nil {
		return nil, fmt.Errorf("load important item effect table: %w", err)
	}
	counts, err := utils.ReadTable[EntityMImportantItemEffectDropCount]("m_important_item_effect_drop_count")
	if err != nil {
		return nil, fmt.Errorf("load important item effect drop count table: %w", err)
	}
	questGroups, err := utils.ReadTable[EntityMImportantItemEffectTargetQuestGroup]("m_important_item_effect_target_quest_group")
	if err != nil {
		return nil, fmt.Errorf("load important item effect target quest group table: %w", err)
	}
	itemGroups, err := utils.ReadTable[EntityMImportantItemEffectTargetItemGroup]("m_important_item_effect_target_item_group")
	if err != nil {
		return nil, fmt.Errorf("load important item effect target item group table: %w", err)
	}
	sequenceGroups, err := utils.ReadTable[EntityMMainQuestSequenceGroup]("m_main_quest_sequence_group")
	if err != nil {
		return nil, fmt.Errorf("load main quest sequence group table: %w", err)
	}
	sequences, err := utils.ReadTable[EntityMMainQuestSequence]("m_main_quest_sequence")
	if err != nil {
		return nil, fmt.Errorf("load main quest sequence table: %w", err)
	}

	effectById := make(map[int32]EntityMImportantItemEffect, len(effects))
	for _, e := range effects {
		effectById[e.ImportantItemEffectId] = e
	}
	countById := make(map[int32]EntityMImportantItemEffectDropCount, len(counts))
	for _, r := range counts {
		countById[r.ImportantItemEffectDropCountId] = r
	}

	c := &ImportantItemEffectCatalog{
		QuestGroups:         make(map[int32][]EntityMImportantItemEffectTargetQuestGroup),
		ItemGroups:          make(map[int32][]EntityMImportantItemEffectTargetItemGroup),
		MainQuestDifficulty: make(map[int32]int32),
	}
	for _, it := range items {
		e, ok := effectById[it.ImportantItemEffectId]
		if !ok || e.ImportantItemEffectType != ImportantItemEffectTypeDropCount {
			continue
		}
		dc, ok := countById[e.ImportantItemEffectTargetId]
		if !ok {
			continue
		}
		c.DropCounts = append(c.DropCounts, ImportantItemDropCount{
			ImportantItemId: it.ImportantItemId,
			GroupingId:      e.ImportantItemEffectGroupingId,
			Priority:        e.Priority,
			StartDatetime:   e.StartDatetime,
			EndDatetime:     e.EndDatetime,
			CountPermil:     dc.CountPermil,
			QuestGroupId:    dc.ImportantItemEffectTargetQuestGroupId,
			ItemGroupId:     dc.ImportantItemEffectTargetItemGroupId,
		})
	}
	sort.Slice(c.DropCounts, func(i, j int) bool { return c.DropCounts[i].ImportantItemId < c.DropCounts[j].ImportantItemId })
	for _, r := range questGroups {
		c.QuestGroups[r.ImportantItemEffectTargetQuestGroupId] = append(c.QuestGroups[r.ImportantItemEffectTargetQuestGroupId], r)
	}
	for _, r := range itemGroups {
		c.ItemGroups[r.ImportantItemEffectTargetItemGroupId] = append(c.ItemGroups[r.ImportantItemEffectTargetItemGroupId], r)
	}
	difficultyBySequence := make(map[int32]int32, len(sequenceGroups))
	for _, g := range sequenceGroups {
		difficultyBySequence[g.MainQuestSequenceId] = g.DifficultyType
	}
	for _, s := range sequences {
		if d, ok := difficultyBySequence[s.MainQuestSequenceId]; ok {
			c.MainQuestDifficulty[s.QuestId] = d
		}
	}
	return c, nil
}

// ItemMatches reports whether a drop is in the effect's target item group
// (group 0 targets every drop).
func (c *ImportantItemEffectCatalog) ItemMatches(itemGroupId, possessionType, possessionId int32) bool {
	if itemGroupId == 0 {
		return true
	}
	for _, r := range c.ItemGroups[itemGroupId] {
		if r.PossessionType == possessionType && r.PossessionId == possessionId {
			return true
		}
	}
	return false
}
