package masterdata

import (
	"fmt"
	"sort"

	"lunar-tear/server/internal/utils"
)

// LimitContentDeckRestrictionType values (what a Recollections of Dusk run
// locks once used).
const (
	LimitContentDeckRestrictionCostume int32 = 1
	LimitContentDeckRestrictionWeapon  int32 = 2
)

// LimitContentSequence is one difficulty of a Recollections of Dusk chapter:
// three quests played in order.
type LimitContentSequence struct {
	EventQuestChapterId int32
	DifficultyType      int32
	QuestIds            []int32
}

type limitContentRestriction struct {
	startDatetime int64
	endDatetime   int64
	types         []int32
}

// LimitContentCatalog holds the Recollections of Dusk (event quest limit
// content) deck rules: which possession types a chapter locks once used
// (m_event_quest_limit_content_deck_restriction*, read by the client's
// CalculatorLimitContent.CreateTermDeckRestrictionTargets) and each quest's
// difficulty sequence.
type LimitContentCatalog struct {
	SequenceByQuestId     map[int32]*LimitContentSequence
	restrictionsByChapter map[int32][]limitContentRestriction
}

func LoadLimitContentCatalog() (*LimitContentCatalog, error) {
	relations, err := utils.ReadTable[EntityMEventQuestChapterLimitContentRelation]("m_event_quest_chapter_limit_content_relation")
	if err != nil {
		return nil, fmt.Errorf("load event quest chapter limit content relation table: %w", err)
	}
	contents, err := utils.ReadTable[EntityMEventQuestLimitContent]("m_event_quest_limit_content")
	if err != nil {
		return nil, fmt.Errorf("load event quest limit content table: %w", err)
	}
	restrictions, err := utils.ReadTable[EntityMEventQuestLimitContentDeckRestriction]("m_event_quest_limit_content_deck_restriction")
	if err != nil {
		return nil, fmt.Errorf("load event quest limit content deck restriction table: %w", err)
	}
	targets, err := utils.ReadTable[EntityMEventQuestLimitContentDeckRestrictionTarget]("m_event_quest_limit_content_deck_restriction_target")
	if err != nil {
		return nil, fmt.Errorf("load event quest limit content deck restriction target table: %w", err)
	}
	chapters, err := utils.ReadTable[EntityMEventQuestChapter]("m_event_quest_chapter")
	if err != nil {
		return nil, fmt.Errorf("load event quest chapter table: %w", err)
	}
	sequenceGroups, err := utils.ReadTable[EntityMEventQuestSequenceGroup]("m_event_quest_sequence_group")
	if err != nil {
		return nil, fmt.Errorf("load event quest sequence group table: %w", err)
	}
	sequences, err := utils.ReadTable[EntityMEventQuestSequence]("m_event_quest_sequence")
	if err != nil {
		return nil, fmt.Errorf("load event quest sequence table: %w", err)
	}
	return BuildLimitContentCatalog(relations, contents, restrictions, targets, chapters, sequenceGroups, sequences), nil
}

// BuildLimitContentCatalog joins the limit content tables.
func BuildLimitContentCatalog(
	relations []EntityMEventQuestChapterLimitContentRelation,
	contents []EntityMEventQuestLimitContent,
	restrictions []EntityMEventQuestLimitContentDeckRestriction,
	targets []EntityMEventQuestLimitContentDeckRestrictionTarget,
	chapters []EntityMEventQuestChapter,
	sequenceGroups []EntityMEventQuestSequenceGroup,
	sequences []EntityMEventQuestSequence,
) *LimitContentCatalog {
	typesByTarget := make(map[int32][]int32)
	for _, t := range targets {
		typesByTarget[t.EventQuestLimitContentDeckRestrictionTargetId] = append(
			typesByTarget[t.EventQuestLimitContentDeckRestrictionTargetId], t.LimitContentDeckRestrictionType)
	}
	restrictionsById := make(map[int32][]limitContentRestriction)
	for _, r := range restrictions {
		restrictionsById[r.EventQuestLimitContentDeckRestrictionId] = append(restrictionsById[r.EventQuestLimitContentDeckRestrictionId],
			limitContentRestriction{
				startDatetime: r.StartDatetime,
				endDatetime:   r.EndDatetime,
				types:         typesByTarget[r.EventQuestLimitContentDeckRestrictionTargetId],
			})
	}
	restrictionByContent := make(map[int32]int32, len(contents))
	for _, c := range contents {
		restrictionByContent[c.EventQuestLimitContentId] = c.EventQuestLimitContentDeckRestrictionId
	}

	cat := &LimitContentCatalog{
		SequenceByQuestId:     make(map[int32]*LimitContentSequence),
		restrictionsByChapter: make(map[int32][]limitContentRestriction),
	}
	isLimitChapter := make(map[int32]bool, len(relations))
	for _, r := range relations {
		isLimitChapter[r.EventQuestChapterId] = true
		cat.restrictionsByChapter[r.EventQuestChapterId] = restrictionsById[restrictionByContent[r.EventQuestLimitContentId]]
	}

	questsBySequence := make(map[int32][]EntityMEventQuestSequence)
	for _, s := range sequences {
		questsBySequence[s.EventQuestSequenceId] = append(questsBySequence[s.EventQuestSequenceId], s)
	}
	groupsById := make(map[int32][]EntityMEventQuestSequenceGroup)
	for _, g := range sequenceGroups {
		groupsById[g.EventQuestSequenceGroupId] = append(groupsById[g.EventQuestSequenceGroupId], g)
	}
	for _, ch := range chapters {
		if !isLimitChapter[ch.EventQuestChapterId] {
			continue
		}
		for _, g := range groupsById[ch.EventQuestSequenceGroupId] {
			rows := questsBySequence[g.EventQuestSequenceId]
			sort.Slice(rows, func(i, j int) bool { return rows[i].SortOrder < rows[j].SortOrder })
			seq := &LimitContentSequence{EventQuestChapterId: ch.EventQuestChapterId, DifficultyType: g.DifficultyType}
			for _, r := range rows {
				seq.QuestIds = append(seq.QuestIds, r.QuestId)
			}
			for _, q := range seq.QuestIds {
				cat.SequenceByQuestId[q] = seq
			}
		}
	}
	return cat
}

// RestrictionTypes lists what a chapter's run locks now (costume and/or
// weapon); empty for a chapter that is not limit content.
func (c *LimitContentCatalog) RestrictionTypes(eventQuestChapterId int32, nowMillis int64) []int32 {
	var out []int32
	for _, r := range c.restrictionsByChapter[eventQuestChapterId] {
		if nowMillis < r.startDatetime || nowMillis > r.endDatetime {
			continue
		}
		out = append(out, r.types...)
	}
	return out
}
