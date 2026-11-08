package masterdata

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"lunar-tear/server/internal/masterdata/memorydb"
)

// A tiny story: season 1 is route 1 (chapter 1: q1 q2, chapter 2: q3);
// season 2 is route 2 (chapter 3: q10 q11) or route 3 (chapter 4: q20);
// season 3 is route 4 (chapter 5: q30 q31).
func testStoryPath() *StoryPath {
	routes := []EntityMMainQuestRoute{
		{MainQuestRouteId: 1, MainQuestSeasonId: 1, SortOrder: 1},
		{MainQuestRouteId: 3, MainQuestSeasonId: 2, SortOrder: 2},
		{MainQuestRouteId: 2, MainQuestSeasonId: 2, SortOrder: 1},
		{MainQuestRouteId: 4, MainQuestSeasonId: 3, SortOrder: 1},
	}
	chapters := []EntityMMainQuestChapter{
		{MainQuestChapterId: 2, MainQuestRouteId: 1, SortOrder: 2, MainQuestSequenceGroupId: 2},
		{MainQuestChapterId: 1, MainQuestRouteId: 1, SortOrder: 1, MainQuestSequenceGroupId: 1},
		{MainQuestChapterId: 3, MainQuestRouteId: 2, SortOrder: 1, MainQuestSequenceGroupId: 3},
		{MainQuestChapterId: 4, MainQuestRouteId: 3, SortOrder: 1, MainQuestSequenceGroupId: 4},
		{MainQuestChapterId: 5, MainQuestRouteId: 4, SortOrder: 1, MainQuestSequenceGroupId: 5},
	}
	var groups []EntityMMainQuestSequenceGroup
	for g := int32(1); g <= 5; g++ {
		groups = append(groups,
			EntityMMainQuestSequenceGroup{MainQuestSequenceGroupId: g, DifficultyType: 1, MainQuestSequenceId: g},
			EntityMMainQuestSequenceGroup{MainQuestSequenceGroupId: g, DifficultyType: 2, MainQuestSequenceId: 100 + g})
	}
	sequences := []EntityMMainQuestSequence{
		{MainQuestSequenceId: 1, SortOrder: 2, QuestId: 2},
		{MainQuestSequenceId: 1, SortOrder: 1, QuestId: 1},
		{MainQuestSequenceId: 2, SortOrder: 1, QuestId: 3},
		{MainQuestSequenceId: 3, SortOrder: 1, QuestId: 10},
		{MainQuestSequenceId: 3, SortOrder: 2, QuestId: 11},
		{MainQuestSequenceId: 4, SortOrder: 1, QuestId: 20},
		{MainQuestSequenceId: 5, SortOrder: 1, QuestId: 30},
		{MainQuestSequenceId: 5, SortOrder: 2, QuestId: 31},
		{MainQuestSequenceId: 101, SortOrder: 1, QuestId: 9001}, // hard: not on the path
	}
	var scenes []EntityMQuestScene
	for i, q := range []int32{1, 2, 3, 10, 11, 20, 30, 31} {
		base := int32(i+1) * 100
		scenes = append(scenes,
			EntityMQuestScene{QuestSceneId: base + 1, QuestId: q, SortOrder: base + 1},
			EntityMQuestScene{QuestSceneId: base, QuestId: q, SortOrder: base})
	}
	return BuildStoryPath(routes, chapters, groups, sequences, scenes)
}

func TestStoryPathOrder(t *testing.T) {
	p := testStoryPath()
	for _, c := range []struct {
		route int32
		want  []int32
	}{{2, []int32{1, 2, 3, 10, 11, 30}}, {3, []int32{1, 2, 3, 20, 30}}} {
		got, err := p.Path(31, c.route)
		if err != nil || !reflect.DeepEqual(got, c.want) {
			t.Fatalf("Path(31, %d) = %v, %v; want %v", c.route, got, err, c.want)
		}
	}
}

func TestStoryPathMidChapter(t *testing.T) {
	p := testStoryPath()
	if got, err := p.Path(2, 2); err != nil || !reflect.DeepEqual(got, []int32{1}) {
		t.Fatalf("Path(2) = %v, %v", got, err)
	}
	if got, err := p.Path(1, 2); err != nil || len(got) != 0 {
		t.Fatalf("Path(1) = %v, %v", got, err)
	}
}

func TestStoryPathSeason2RouteMustMatch(t *testing.T) {
	p := testStoryPath()
	if _, err := p.Path(20, 2); err == nil {
		t.Fatal("a route-3 quest through route 2 was accepted")
	}
	if _, err := p.Path(9001, 2); err == nil {
		t.Fatal("a hard quest was accepted")
	}
}

func TestStoryPathFirstScene(t *testing.T) {
	p := testStoryPath()
	if p.FirstScene[1] != 100 || p.SceneQuest[101] != 1 || p.ChapterOf[11] != 3 || p.RouteOf[20] != 3 {
		t.Fatalf("first scene %d, scene quest %d, chapter %d, route %d", p.FirstScene[1], p.SceneQuest[101], p.ChapterOf[11], p.RouteOf[20])
	}
	if !reflect.DeepEqual(p.Seasons[2], []int32{2, 3}) {
		t.Fatalf("season 2 routes %v", p.Seasons[2])
	}
}

// Both game versions: BUNKER_TEST_MASTER (Global) and BUNKER_TEST_MASTER_JP
// (Japanese) share the story's structure.
func TestStoryPathRealData(t *testing.T) {
	ran := false
	for _, env := range []string{"BUNKER_TEST_MASTER", "BUNKER_TEST_MASTER_JP"} {
		master := os.Getenv(env)
		if master == "" {
			continue
		}
		ran = true
		t.Run(env, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "master.bin.e")
			data, err := os.ReadFile(master)
			if err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(path, data, 0o600); err != nil {
				t.Fatal(err)
			}
			if err := memorydb.Init(path); err != nil {
				t.Fatal(err)
			}
			p, err := LoadStoryPath()
			if err != nil {
				t.Fatal(err)
			}
			chapters, quests := 0, 0
			for _, cs := range p.Chapters {
				chapters += len(cs)
				for _, c := range cs {
					quests += len(c.QuestIds)
				}
			}
			if len(p.Chapters) != 4 || chapters != 38 || quests != 281 {
				t.Fatalf("%d routes, %d chapters, %d quests", len(p.Chapters), chapters, quests)
			}
			if p.FirstScene[305] != 611 || p.ChapterOf[305] != 16 {
				t.Fatalf("quest 305: first scene %d, chapter %d", p.FirstScene[305], p.ChapterOf[305])
			}
			path31, err := p.Path(p.Chapters[4][0].QuestIds[0], 3)
			if err != nil || len(path31) != 110+62 {
				t.Fatalf("path to season 3 through route 3: %d quests, %v", len(path31), err)
			}
		})
	}
	if !ran {
		t.Skip("BUNKER_TEST_MASTER and BUNKER_TEST_MASTER_JP not set")
	}
}
