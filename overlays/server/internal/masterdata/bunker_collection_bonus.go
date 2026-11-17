package masterdata

import (
	"log"
	"sort"

	"lunar-tear/server/internal/bunkercache"
	"lunar-tear/server/internal/utils"
)

// Costume collection bonuses (m_costume_collection_bonus): owning every
// costume of a set gives a bonus on main-story chapters, stronger as the set
// ascends ("Unlocked by ascending all characters {0} or more times").

// CollectionBonusEffectType values (m_collection_bonus_effect), matching the
// bonus texts.
const (
	CollectionBonusCostumeExp int32 = 2
	CollectionBonusDropRate   int32 = 3
	CollectionBonusGold       int32 = 4
)

// collectionAssignmentMainChapter is QuestAssignmentType for a main-quest
// chapter (MainQuestChapterId), the only type a bonus uses.
const collectionAssignmentMainChapter int32 = 2

// CollectionBonus is one bonus: its set, the amount at each level (the
// lowest limit break across the set, 0–4), in percent, and its chapters.
type CollectionBonus struct {
	Id, GroupingId, EffectType int32
	Costumes                   []int32
	Amounts                    [5]int32
	MainChapters               map[int32]bool
	StartDatetime, EndDatetime int64
}

type collectionBonusTables struct {
	bonuses     []EntityMCostumeCollectionBonus
	groups      []EntityMCostumeCollectionBonusGroup
	effects     []EntityMCollectionBonusEffect
	assignments []EntityMCollectionBonusQuestAssignment
	assignGroup []EntityMCollectionBonusQuestAssignmentGroup
}

var CollectionBonuses = bunkercache.Value(func() []CollectionBonus {
	var t collectionBonusTables
	var err error
	read := func(name string) {
		if err != nil {
			log.Printf("[CollectionBonuses] %s: %v", name, err)
		}
	}
	t.bonuses, err = utils.ReadTable[EntityMCostumeCollectionBonus]("m_costume_collection_bonus")
	read("m_costume_collection_bonus")
	t.groups, err = utils.ReadTable[EntityMCostumeCollectionBonusGroup]("m_costume_collection_bonus_group")
	read("m_costume_collection_bonus_group")
	t.effects, err = utils.ReadTable[EntityMCollectionBonusEffect]("m_collection_bonus_effect")
	read("m_collection_bonus_effect")
	t.assignments, err = utils.ReadTable[EntityMCollectionBonusQuestAssignment]("m_collection_bonus_quest_assignment")
	read("m_collection_bonus_quest_assignment")
	t.assignGroup, err = utils.ReadTable[EntityMCollectionBonusQuestAssignmentGroup]("m_collection_bonus_quest_assignment_group")
	read("m_collection_bonus_quest_assignment_group")
	return collectionBonuses(t)
})

func collectionBonuses(t collectionBonusTables) []CollectionBonus {
	costumes := map[int32][]int32{}
	for _, g := range t.groups {
		costumes[g.CollectionBonusGroupId] = append(costumes[g.CollectionBonusGroupId], g.CostumeId)
	}
	effects := map[int32]EntityMCollectionBonusEffect{}
	for _, e := range t.effects {
		effects[e.CollectionBonusEffectId] = e
	}
	chapterOf := map[int32]int32{}
	for _, a := range t.assignments {
		if a.QuestAssignmentType == collectionAssignmentMainChapter {
			chapterOf[a.CollectionBonusQuestAssignmentId] = a.MainQuestChapterId
		}
	}
	chapters := map[int32]map[int32]bool{}
	for _, g := range t.assignGroup {
		ch, ok := chapterOf[g.CollectionBonusQuestAssignmentId]
		if !ok {
			continue
		}
		if chapters[g.CollectionBonusQuestAssignmentGroupId] == nil {
			chapters[g.CollectionBonusQuestAssignmentGroupId] = map[int32]bool{}
		}
		chapters[g.CollectionBonusQuestAssignmentGroupId][ch] = true
	}
	var out []CollectionBonus
	for _, b := range t.bonuses {
		e, ok := effects[b.CollectionBonusEffectId]
		set := costumes[b.CollectionBonusGroupId]
		if !ok || len(set) == 0 || len(chapters[b.CollectionBonusQuestAssignmentGroupId]) == 0 {
			continue
		}
		sorted := append([]int32(nil), set...)
		sort.Slice(sorted, func(i, j int) bool { return sorted[i] < sorted[j] })
		out = append(out, CollectionBonus{
			Id:            b.CollectionBonusId,
			GroupingId:    b.GroupingId,
			EffectType:    e.CollectionBonusEffectType,
			Costumes:      sorted,
			Amounts:       [5]int32{e.Amount00, e.Amount01, e.Amount02, e.Amount03, e.Amount04},
			MainChapters:  chapters[b.CollectionBonusQuestAssignmentGroupId],
			StartDatetime: b.StartDatetime,
			EndDatetime:   b.EndDatetime,
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Id < out[j].Id })
	return out
}

// MainQuestChapters maps every main-story quest to its chapter: each
// difficulty (m_main_quest_sequence_group), and each story replay through the
// quest it replays (m_quest_relation_main_flow). QuestCatalog's own map keeps
// Normal quests only.
var MainQuestChapters = bunkercache.Value(func() map[int32]int32 {
	var t mainQuestChapterTables
	var err error
	read := func(name string) {
		if err != nil {
			log.Printf("[MainQuestChapters] %s: %v", name, err)
		}
	}
	t.chapters, err = utils.ReadTable[EntityMMainQuestChapter]("m_main_quest_chapter")
	read("m_main_quest_chapter")
	t.groups, err = utils.ReadTable[EntityMMainQuestSequenceGroup]("m_main_quest_sequence_group")
	read("m_main_quest_sequence_group")
	t.sequences, err = utils.ReadTable[EntityMMainQuestSequence]("m_main_quest_sequence")
	read("m_main_quest_sequence")
	t.relations, err = utils.ReadTable[EntityMQuestRelationMainFlow]("m_quest_relation_main_flow")
	read("m_quest_relation_main_flow")
	return mainQuestChapters(t)
})

type mainQuestChapterTables struct {
	chapters  []EntityMMainQuestChapter
	groups    []EntityMMainQuestSequenceGroup
	sequences []EntityMMainQuestSequence
	relations []EntityMQuestRelationMainFlow
}

func mainQuestChapters(t mainQuestChapterTables) map[int32]int32 {
	chapterOfGroup := map[int32]int32{}
	for _, c := range t.chapters {
		chapterOfGroup[c.MainQuestSequenceGroupId] = c.MainQuestChapterId
	}
	chapterOfSequence := map[int32]int32{}
	for _, g := range t.groups {
		if ch, ok := chapterOfGroup[g.MainQuestSequenceGroupId]; ok {
			chapterOfSequence[g.MainQuestSequenceId] = ch
		}
	}
	out := map[int32]int32{}
	for _, s := range t.sequences {
		if ch, ok := chapterOfSequence[s.MainQuestSequenceId]; ok {
			out[s.QuestId] = ch
		}
	}
	for _, r := range t.relations {
		if ch, ok := out[r.MainFlowQuestId]; ok && r.ReplayFlowQuestId != 0 {
			if _, mapped := out[r.ReplayFlowQuestId]; !mapped {
				out[r.ReplayFlowQuestId] = ch
			}
		}
	}
	return out
}
