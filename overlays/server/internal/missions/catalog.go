// Package missions tracks the game's missions (daily, challenge, special,
// mission pass) and pays their rewards. Lunar Tear only tracks the missions
// inside quests; these were left at 0.
//
// What a mission counts comes from the master data (MissionClearConditionType);
// which quests, costumes or weapons it counts comes from rules.json, generated
// from the missions' names by scripts/gen_mission_rules.py, because the original
// server's filter tables are not in the master data.
package missions

import (
	_ "embed"
	"encoding/json"
	"log"
	"sync"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/utils"
)

// MissionCategoryType values from the game client.
const (
	CategoryDaily              = 1
	CategoryMissionPassDaily   = 9
	CategoryMissionPassSpecial = 10
)

// MissionProgressStatusType values from the game client.
const (
	StatusInProgress     = 1
	StatusClear          = 2
	StatusRewardReceived = 9
)

//go:embed rules.json
var rulesJSON []byte

// QuestFilter selects the quests a quest-clear mission counts. The kinds (Main,
// Event, EventTypes, EventChapters, MainChapters, DailyLimited) are alternatives;
// with none set, every quest counts. Diff, Order and Characters narrow further.
type QuestFilter struct {
	Main          bool    `json:"main"`
	Event         bool    `json:"event"`
	EventTypes    []int32 `json:"event_types"`
	EventChapters []int32 `json:"event_chapters"`
	MainChapters  []int32 `json:"main_chapters"`
	DailyLimited  bool    `json:"daily_limited"`
	Diff          []int32 `json:"diff"`
	Order         int32   `json:"order"`
	Characters    []int32 `json:"characters"`
}

type Rule struct {
	MissionId  int32        `json:"id"`
	Kind       string       `json:"k"`
	Quest      *QuestFilter `json:"q"`
	Costumes   []int32      `json:"c"` // negative: any costume of that character
	Weapons    []int32      `json:"w"`
	Characters []int32      `json:"ch"`
	NoSkip     bool         `json:"ns"`
	Gacha      string       `json:"g"`
}

type Mission struct {
	masterdata.EntityMMission
	Rule          Rule
	Category      int32
	SubCategoryId int32
	Start, End    int64
	Unlock        masterdata.EntityMMissionUnlockCondition
}

// Daily missions start again every day.
func (m *Mission) Daily() bool {
	return m.Category == CategoryDaily || m.Category == CategoryMissionPassDaily
}

// questPlace is where a quest sits: main story chapter or event chapter, with
// its difficulty and its place in the chapter (1-based).
type questPlace struct {
	MainChapter  int32
	EventChapter int32
	EventType    int32
	Difficulty   int32
	Order        int32
}

type Catalog struct {
	Missions      []*Mission
	ByKind        map[string][]*Mission
	ById          map[int32]*Mission
	Rewards       map[int32][]masterdata.EntityMMissionReward
	Passes        map[int32]masterdata.EntityMMissionPass
	PassByGroup   map[int32]int32 // MissionGroupId -> MissionPassId
	PassLevels    map[int32][]masterdata.EntityMMissionPassLevelGroup
	PassRewards   map[int32][]masterdata.EntityMMissionPassRewardGroup
	QuestStamina  map[int32]int32
	QuestDailyMax map[int32]int32
	places        map[int32][]questPlace
	chapterChars  map[int32][]int32 // event chapter -> characters
	costumeChar   map[int32]int32
}

var (
	cacheMu sync.Mutex
	cache   = map[*runtime.Catalogs]*Catalog{}
	holder  *runtime.Holder
)

// SetHolder gives the package the server's master data.
func SetHolder(h *runtime.Holder) { holder = h }

// Current is the catalog for the master data in use, or nil before SetHolder.
func Current() *Catalog {
	if holder == nil {
		return nil
	}
	cats := holder.Get()
	cacheMu.Lock()
	defer cacheMu.Unlock()
	if c, ok := cache[cats]; ok {
		return c
	}
	c, err := load()
	if err != nil {
		log.Printf("[missions] load: %v", err)
		return nil
	}
	clear(cache) // master data was reloaded: drop the old catalog
	cache[cats] = c
	return c
}

func read[T any](key string) []T {
	rows, err := utils.ReadTable[T](key)
	if err != nil {
		log.Printf("[missions] read %s: %v", key, err)
	}
	return rows
}

func load() (*Catalog, error) {
	var rules []Rule
	if err := json.Unmarshal(rulesJSON, &rules); err != nil {
		return nil, err
	}
	ruleById := make(map[int32]Rule, len(rules))
	for _, r := range rules {
		ruleById[r.MissionId] = r
	}
	groups := map[int32]masterdata.EntityMMissionGroup{}
	for _, g := range read[masterdata.EntityMMissionGroup]("m_mission_group") {
		groups[g.MissionGroupId] = g
	}
	terms := map[int32]masterdata.EntityMMissionTerm{}
	for _, t := range read[masterdata.EntityMMissionTerm]("m_mission_term") {
		terms[t.MissionTermId] = t
	}
	unlocks := map[int32]masterdata.EntityMMissionUnlockCondition{}
	for _, u := range read[masterdata.EntityMMissionUnlockCondition]("m_mission_unlock_condition") {
		unlocks[u.MissionUnlockConditionId] = u
	}
	c := &Catalog{
		ByKind:        map[string][]*Mission{},
		ById:          map[int32]*Mission{},
		Rewards:       map[int32][]masterdata.EntityMMissionReward{},
		Passes:        map[int32]masterdata.EntityMMissionPass{},
		PassByGroup:   map[int32]int32{},
		PassLevels:    map[int32][]masterdata.EntityMMissionPassLevelGroup{},
		PassRewards:   map[int32][]masterdata.EntityMMissionPassRewardGroup{},
		QuestStamina:  map[int32]int32{},
		QuestDailyMax: map[int32]int32{},
		places:        map[int32][]questPlace{},
		chapterChars:  map[int32][]int32{},
		costumeChar:   map[int32]int32{},
	}
	for _, row := range read[masterdata.EntityMMission]("m_mission") {
		g := groups[row.MissionGroupId]
		t := terms[row.MissionTermId]
		m := &Mission{EntityMMission: row, Category: g.MissionCategoryType, SubCategoryId: g.MissionSubCategoryId,
			Start: t.StartDatetime, End: t.EndDatetime, Unlock: unlocks[row.MissionUnlockConditionId]}
		if r, ok := ruleById[row.MissionId]; ok {
			m.Rule = r
			c.ByKind[r.Kind] = append(c.ByKind[r.Kind], m)
		}
		c.Missions = append(c.Missions, m)
		c.ById[row.MissionId] = m
	}
	for _, r := range read[masterdata.EntityMMissionReward]("m_mission_reward") {
		c.Rewards[r.MissionRewardId] = append(c.Rewards[r.MissionRewardId], r)
	}
	for _, p := range read[masterdata.EntityMMissionPass]("m_mission_pass") {
		c.Passes[p.MissionPassId] = p
	}
	for _, g := range read[masterdata.EntityMMissionPassMissionGroup]("m_mission_pass_mission_group") {
		c.PassByGroup[g.MissionGroupId] = g.MissionPassId
	}
	for _, l := range read[masterdata.EntityMMissionPassLevelGroup]("m_mission_pass_level_group") {
		c.PassLevels[l.MissionPassLevelGroupId] = append(c.PassLevels[l.MissionPassLevelGroupId], l)
	}
	for _, r := range read[masterdata.EntityMMissionPassRewardGroup]("m_mission_pass_reward_group") {
		c.PassRewards[r.MissionPassRewardGroupId] = append(c.PassRewards[r.MissionPassRewardGroupId], r)
	}
	for _, q := range read[masterdata.EntityMQuest]("m_quest") {
		c.QuestStamina[q.QuestId] = q.Stamina
		c.QuestDailyMax[q.QuestId] = q.DailyClearableCount
	}

	// Main story: chapter -> sequence group (one per difficulty) -> quests in order.
	mainSeq := map[int32][]masterdata.EntityMMainQuestSequence{}
	for _, s := range read[masterdata.EntityMMainQuestSequence]("m_main_quest_sequence") {
		mainSeq[s.MainQuestSequenceId] = append(mainSeq[s.MainQuestSequenceId], s)
	}
	mainGroups := map[int32][]masterdata.EntityMMainQuestSequenceGroup{}
	for _, g := range read[masterdata.EntityMMainQuestSequenceGroup]("m_main_quest_sequence_group") {
		mainGroups[g.MainQuestSequenceGroupId] = append(mainGroups[g.MainQuestSequenceGroupId], g)
	}
	for _, ch := range read[masterdata.EntityMMainQuestChapter]("m_main_quest_chapter") {
		for _, g := range mainGroups[ch.MainQuestSequenceGroupId] {
			for _, s := range mainSeq[g.MainQuestSequenceId] {
				c.places[s.QuestId] = append(c.places[s.QuestId], questPlace{MainChapter: ch.MainQuestChapterId, Difficulty: g.DifficultyType, Order: s.SortOrder})
			}
		}
	}
	// Events: chapter -> sequence group (one per difficulty) -> quests in order.
	eventSeq := map[int32][]masterdata.EntityMEventQuestSequence{}
	for _, s := range read[masterdata.EntityMEventQuestSequence]("m_event_quest_sequence") {
		eventSeq[s.EventQuestSequenceId] = append(eventSeq[s.EventQuestSequenceId], s)
	}
	eventGroups := map[int32][]masterdata.EntityMEventQuestSequenceGroup{}
	for _, g := range read[masterdata.EntityMEventQuestSequenceGroup]("m_event_quest_sequence_group") {
		eventGroups[g.EventQuestSequenceGroupId] = append(eventGroups[g.EventQuestSequenceGroupId], g)
	}
	for _, ch := range read[masterdata.EntityMEventQuestChapter]("m_event_quest_chapter") {
		for _, g := range eventGroups[ch.EventQuestSequenceGroupId] {
			for _, s := range eventSeq[g.EventQuestSequenceId] {
				c.places[s.QuestId] = append(c.places[s.QuestId], questPlace{EventChapter: ch.EventQuestChapterId, EventType: ch.EventQuestType, Difficulty: g.DifficultyType, Order: s.SortOrder})
			}
		}
	}
	for _, cc := range read[masterdata.EntityMEventQuestChapterCharacter]("m_event_quest_chapter_character") {
		c.chapterChars[cc.EventQuestChapterId] = append(c.chapterChars[cc.EventQuestChapterId], cc.CharacterId)
	}
	for _, co := range read[masterdata.EntityMCostume]("m_costume") {
		c.costumeChar[co.CostumeId] = co.CharacterId
	}
	limitCostume := map[int32]int32{}
	for _, l := range read[masterdata.EntityMEventQuestLimitContent]("m_event_quest_limit_content") {
		limitCostume[l.EventQuestLimitContentId] = l.CostumeId
	}
	for _, r := range read[masterdata.EntityMEventQuestChapterLimitContentRelation]("m_event_quest_chapter_limit_content_relation") {
		if ch := c.costumeChar[limitCostume[r.EventQuestLimitContentId]]; ch != 0 {
			c.chapterChars[r.EventQuestChapterId] = append(c.chapterChars[r.EventQuestChapterId], ch)
		}
	}
	log.Printf("[missions] %d missions, %d with rules", len(c.Missions), len(rules))
	return c, nil
}

func contains(list []int32, v int32) bool {
	for _, x := range list {
		if x == v {
			return true
		}
	}
	return false
}

// QuestMatches reports whether clearing questId counts for the filter.
func (c *Catalog) QuestMatches(f *QuestFilter, questId int32) bool {
	if f == nil {
		return true
	}
	places := c.places[questId]
	kinds := f.Main || f.Event || len(f.EventTypes) > 0 || len(f.EventChapters) > 0 || len(f.MainChapters) > 0 || f.DailyLimited
	if len(places) == 0 {
		// Quests outside both trees (extra quests, subjugation): only an unfiltered count includes them.
		return !kinds && len(f.Diff) == 0 && f.Order == 0 && len(f.Characters) == 0
	}
	for _, p := range places {
		if kinds {
			ok := (f.Main && p.MainChapter != 0) ||
				(f.Event && p.EventChapter != 0) ||
				(p.EventChapter != 0 && contains(f.EventTypes, p.EventType)) ||
				(p.EventChapter != 0 && contains(f.EventChapters, p.EventChapter)) ||
				(p.MainChapter != 0 && contains(f.MainChapters, p.MainChapter)) ||
				(f.DailyLimited && c.QuestDailyMax[questId] > 0)
			if !ok {
				continue
			}
		}
		if len(f.Diff) > 0 && !contains(f.Diff, p.Difficulty) {
			continue
		}
		if f.Order != 0 && p.Order != f.Order {
			continue
		}
		if len(f.Characters) > 0 {
			found := false
			for _, ch := range c.chapterChars[p.EventChapter] {
				found = found || contains(f.Characters, ch)
			}
			if !found {
				continue
			}
		}
		return true
	}
	return false
}

// CostumeMatches reports whether a costume satisfies a rule's costume list.
func (c *Catalog) CostumeMatches(list []int32, costumeId int32) bool {
	if len(list) == 0 {
		return true
	}
	for _, id := range list {
		if id == costumeId || (id < 0 && c.costumeChar[costumeId] == -id) {
			return true
		}
	}
	return false
}
