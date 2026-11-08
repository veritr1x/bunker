package masterdata

import (
	"fmt"
	"sort"

	"lunar-tear/server/internal/utils"
)

// Bunker: Pod Programs › Story Jump. The main story in play order: season 1
// is route 1; season 2 is route 2 or route 3 (the player picks one); season 3
// is route 4. Only the main flow (difficulty 1) is on the path.

type StoryChapter struct {
	ChapterId, RouteId, SeasonId int32
	QuestIds                     []int32 // in sequence SortOrder
}

type StoryPath struct {
	Seasons    map[int32][]int32        // season -> route ids by route SortOrder
	Chapters   map[int32][]StoryChapter // route -> chapters by chapter SortOrder
	ChapterOf  map[int32]int32          // quest -> chapter
	RouteOf    map[int32]int32          // quest -> route
	FirstScene map[int32]int32          // quest -> its lowest-SortOrder scene
	SceneQuest map[int32]int32          // scene -> quest (main-flow quests only)
	SceneOrder map[int32]int32          // scene -> SortOrder (main-flow quests only)
	seasonOf   map[int32]int32          // route -> season
}

func BuildStoryPath(routes []EntityMMainQuestRoute, chapters []EntityMMainQuestChapter, groups []EntityMMainQuestSequenceGroup, sequences []EntityMMainQuestSequence, scenes []EntityMQuestScene) *StoryPath {
	p := &StoryPath{
		Seasons:    map[int32][]int32{},
		Chapters:   map[int32][]StoryChapter{},
		ChapterOf:  map[int32]int32{},
		RouteOf:    map[int32]int32{},
		FirstScene: map[int32]int32{},
		SceneQuest: map[int32]int32{},
		SceneOrder: map[int32]int32{},
		seasonOf:   map[int32]int32{},
	}
	sortedRoutes := append([]EntityMMainQuestRoute(nil), routes...)
	sort.SliceStable(sortedRoutes, func(i, j int) bool { return sortedRoutes[i].SortOrder < sortedRoutes[j].SortOrder })
	for _, r := range sortedRoutes {
		p.Seasons[r.MainQuestSeasonId] = append(p.Seasons[r.MainQuestSeasonId], r.MainQuestRouteId)
		p.seasonOf[r.MainQuestRouteId] = r.MainQuestSeasonId
	}
	mainSequence := map[int32]int32{} // sequence group -> difficulty-1 sequence
	for _, g := range groups {
		if g.DifficultyType == 1 {
			mainSequence[g.MainQuestSequenceGroupId] = g.MainQuestSequenceId
		}
	}
	bySequence := map[int32][]EntityMMainQuestSequence{}
	for _, s := range sequences {
		bySequence[s.MainQuestSequenceId] = append(bySequence[s.MainQuestSequenceId], s)
	}
	sortedChapters := append([]EntityMMainQuestChapter(nil), chapters...)
	sort.SliceStable(sortedChapters, func(i, j int) bool { return sortedChapters[i].SortOrder < sortedChapters[j].SortOrder })
	for _, c := range sortedChapters {
		seq, ok := mainSequence[c.MainQuestSequenceGroupId]
		if !ok {
			continue
		}
		rows := append([]EntityMMainQuestSequence(nil), bySequence[seq]...)
		sort.SliceStable(rows, func(i, j int) bool { return rows[i].SortOrder < rows[j].SortOrder })
		ch := StoryChapter{ChapterId: c.MainQuestChapterId, RouteId: c.MainQuestRouteId, SeasonId: p.seasonOf[c.MainQuestRouteId]}
		for _, r := range rows {
			ch.QuestIds = append(ch.QuestIds, r.QuestId)
			p.ChapterOf[r.QuestId] = c.MainQuestChapterId
			p.RouteOf[r.QuestId] = c.MainQuestRouteId
		}
		p.Chapters[c.MainQuestRouteId] = append(p.Chapters[c.MainQuestRouteId], ch)
	}
	firstOrder := map[int32]int32{}
	for _, s := range scenes {
		if _, ok := p.ChapterOf[s.QuestId]; !ok {
			continue
		}
		p.SceneQuest[s.QuestSceneId] = s.QuestId
		p.SceneOrder[s.QuestSceneId] = s.SortOrder
		if o, ok := firstOrder[s.QuestId]; !ok || s.SortOrder < o {
			firstOrder[s.QuestId] = s.SortOrder
			p.FirstScene[s.QuestId] = s.QuestSceneId
		}
	}
	return p
}

func LoadStoryPath() (*StoryPath, error) {
	routes, err := utils.ReadTable[EntityMMainQuestRoute]("m_main_quest_route")
	if err != nil {
		return nil, fmt.Errorf("load main quest routes: %w", err)
	}
	chapters, err := utils.ReadTable[EntityMMainQuestChapter]("m_main_quest_chapter")
	if err != nil {
		return nil, fmt.Errorf("load main quest chapters: %w", err)
	}
	groups, err := utils.ReadTable[EntityMMainQuestSequenceGroup]("m_main_quest_sequence_group")
	if err != nil {
		return nil, fmt.Errorf("load main quest sequence groups: %w", err)
	}
	sequences, err := utils.ReadTable[EntityMMainQuestSequence]("m_main_quest_sequence")
	if err != nil {
		return nil, fmt.Errorf("load main quest sequences: %w", err)
	}
	scenes, err := utils.ReadTable[EntityMQuestScene]("m_quest_scene")
	if err != nil {
		return nil, fmt.Errorf("load quest scenes: %w", err)
	}
	return BuildStoryPath(routes, chapters, groups, sequences, scenes), nil
}

// SeasonOf is the season of a main-story quest (0 if it isn't one).
func (p *StoryPath) SeasonOf(questId int32) int32 {
	return p.seasonOf[p.RouteOf[questId]]
}

// Path is the main-story quests before targetQuest, in play order, going
// through season2Route (2 or 3) when the target is past season 1.
func (p *StoryPath) Path(targetQuest, season2Route int32) ([]int32, error) {
	targetRoute, ok := p.RouteOf[targetQuest]
	if !ok {
		return nil, fmt.Errorf("quest %d is not a main-story quest", targetQuest)
	}
	targetSeason := p.seasonOf[targetRoute]
	var routes []int32
	for season := int32(1); season <= targetSeason; season++ {
		ids := p.Seasons[season]
		if len(ids) <= 1 {
			routes = append(routes, ids...)
			continue
		}
		found := false
		for _, r := range ids {
			if r == season2Route {
				found = true
			}
		}
		if !found {
			return nil, fmt.Errorf("route %d is not a route of season %d", season2Route, season)
		}
		if season == targetSeason && targetRoute != season2Route {
			return nil, fmt.Errorf("quest %d is on route %d, not route %d", targetQuest, targetRoute, season2Route)
		}
		routes = append(routes, season2Route)
	}
	var out []int32
	for _, r := range routes {
		for _, c := range p.Chapters[r] {
			for _, q := range c.QuestIds {
				if q == targetQuest {
					return out, nil
				}
				out = append(out, q)
			}
		}
	}
	return nil, fmt.Errorf("quest %d is not on route %d's path", targetQuest, targetRoute)
}
