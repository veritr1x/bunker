package questflow

import (
	"errors"
	"reflect"
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// The story of masterdata's story path test: season 1 route 1 (chapter 1: q1
// q2, chapter 2: q3), season 2 route 2 (chapter 3: q10 q11) or route 3
// (chapter 4: q20), season 3 route 4 (chapter 5: q30 q31). Quest q's scenes
// are 100*i and 100*i+1 (i its position in that list, from 1).
var storyQuests = []int32{1, 2, 3, 10, 11, 20, 30, 31}

func storyScene(q int32) int32 {
	for i, id := range storyQuests {
		if id == q {
			return int32(i+1) * 100
		}
	}
	panic(q)
}

func storyFixture() (*QuestHandler, *masterdata.StoryPath) {
	routes := []masterdata.EntityMMainQuestRoute{
		{MainQuestRouteId: 1, MainQuestSeasonId: 1, SortOrder: 1},
		{MainQuestRouteId: 2, MainQuestSeasonId: 2, SortOrder: 1},
		{MainQuestRouteId: 3, MainQuestSeasonId: 2, SortOrder: 2},
		{MainQuestRouteId: 4, MainQuestSeasonId: 3, SortOrder: 1},
	}
	chapters := []masterdata.EntityMMainQuestChapter{
		{MainQuestChapterId: 1, MainQuestRouteId: 1, SortOrder: 1, MainQuestSequenceGroupId: 1},
		{MainQuestChapterId: 2, MainQuestRouteId: 1, SortOrder: 2, MainQuestSequenceGroupId: 2},
		{MainQuestChapterId: 3, MainQuestRouteId: 2, SortOrder: 1, MainQuestSequenceGroupId: 3},
		{MainQuestChapterId: 4, MainQuestRouteId: 3, SortOrder: 1, MainQuestSequenceGroupId: 4},
		{MainQuestChapterId: 5, MainQuestRouteId: 4, SortOrder: 1, MainQuestSequenceGroupId: 5},
	}
	var groups []masterdata.EntityMMainQuestSequenceGroup
	for g := int32(1); g <= 5; g++ {
		groups = append(groups, masterdata.EntityMMainQuestSequenceGroup{MainQuestSequenceGroupId: g, DifficultyType: 1, MainQuestSequenceId: g})
	}
	sequences := []masterdata.EntityMMainQuestSequence{
		{MainQuestSequenceId: 1, SortOrder: 1, QuestId: 1}, {MainQuestSequenceId: 1, SortOrder: 2, QuestId: 2},
		{MainQuestSequenceId: 2, SortOrder: 1, QuestId: 3},
		{MainQuestSequenceId: 3, SortOrder: 1, QuestId: 10}, {MainQuestSequenceId: 3, SortOrder: 2, QuestId: 11},
		{MainQuestSequenceId: 4, SortOrder: 1, QuestId: 20},
		{MainQuestSequenceId: 5, SortOrder: 1, QuestId: 30}, {MainQuestSequenceId: 5, SortOrder: 2, QuestId: 31},
	}
	cat := &masterdata.QuestCatalog{
		QuestById:                  map[int32]masterdata.EntityMQuest{},
		SceneById:                  map[int32]masterdata.EntityMQuestScene{},
		MissionById:                map[int32]masterdata.EntityMQuestMission{},
		MissionIdsByQuestId:        map[int32][]int32{},
		MissionRewardsByMissionId:  map[int32][]masterdata.EntityMQuestMissionReward{},
		FirstClearRewardsByGroupId: map[int32][]masterdata.EntityMQuestFirstClearRewardGroup{},
		SceneGrantsBySceneId:       map[int32][]masterdata.EntityMUserQuestSceneGrantPossession{},
	}
	var scenes []masterdata.EntityMQuestScene
	for _, q := range storyQuests {
		cat.QuestById[q] = masterdata.EntityMQuest{QuestId: q, QuestFirstClearRewardGroupId: q, IsCountedAsQuest: true}
		for _, s := range []int32{storyScene(q), storyScene(q) + 1} {
			row := masterdata.EntityMQuestScene{QuestSceneId: s, QuestId: q, SortOrder: s}
			scenes = append(scenes, row)
			cat.SceneById[s] = row
		}
	}
	// q3 gives a companion, q10 gems, q2 an important item.
	cat.FirstClearRewardsByGroupId[3] = []masterdata.EntityMQuestFirstClearRewardGroup{{QuestFirstClearRewardGroupId: 3, PossessionType: int32(model.PossessionTypeCompanion), PossessionId: 7, Count: 1}}
	cat.FirstClearRewardsByGroupId[10] = []masterdata.EntityMQuestFirstClearRewardGroup{{QuestFirstClearRewardGroupId: 10, PossessionType: int32(model.PossessionTypeFreeGem), PossessionId: 0, Count: 500}}
	cat.FirstClearRewardsByGroupId[2] = []masterdata.EntityMQuestFirstClearRewardGroup{{QuestFirstClearRewardGroupId: 2, PossessionType: int32(model.PossessionTypeImportantItem), PossessionId: 100001, Count: 1}}
	// The companion-choice tutorial unlocks on reaching q2's first scene.
	cat.TutorialUnlockConditions = []masterdata.EntityMTutorialUnlockCondition{
		{TutorialType: int32(model.TutorialTypeCompanion), TutorialUnlockConditionType: 2, ConditionValue: storyScene(2)},
		{TutorialType: 9, TutorialUnlockConditionType: 1},
	}
	h := &QuestHandler{QuestCatalog: cat, Config: &masterdata.GameConfig{}, Granter: &store.PossessionGranter{}}
	return h, masterdata.BuildStoryPath(routes, chapters, groups, sequences, scenes)
}

// A save past the opening: one costume, the head at q1's first scene.
func storyUser() *store.UserState {
	u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	u.Costumes["c1"] = store.CostumeState{UserCostumeUuid: "c1", CostumeId: 1}
	u.MainQuest.HeadQuestSceneId = storyScene(1)
	u.MainQuest.CurrentQuestSceneId = storyScene(1)
	u.MainQuest.CurrentMainQuestRouteId = 1
	u.MainQuest.MainQuestSeasonId = 1
	return u
}

func clearQuest(u *store.UserState, q int32) {
	u.Quests[q] = store.UserQuestState{QuestId: q, QuestStateType: model.UserQuestStateTypeCleared, ClearCount: 1, IsRewardGranted: true}
}

func TestJumpToChapterStart(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	res, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 31, Season2Route: 2}, 1000)
	if err != nil {
		t.Fatal(err)
	}
	if want := []int32{1, 2, 3, 10, 11, 30}; !reflect.DeepEqual(res.Cleared, want) {
		t.Fatalf("cleared %v, want %v", res.Cleared, want)
	}
	for _, q := range res.Cleared {
		if qs := u.Quests[q]; qs.QuestStateType != model.UserQuestStateTypeCleared || qs.ClearCount != 1 || !qs.IsRewardGranted {
			t.Fatalf("quest %d: %+v", q, qs)
		}
	}
	if _, ok := u.Quests[31]; ok {
		t.Fatal("the target quest has a row")
	}
	if _, ok := u.Quests[20]; ok {
		t.Fatal("route 3 was cleared on a route-2 jump")
	}
	// q3's companion and the companion tutorial's (its scene is on the path).
	if len(u.Companions) != 2 || u.Gem.FreeGem != 500 || u.ImportantItems[100001] != 1 {
		t.Fatalf("companions %d, gems %d, item %d", len(u.Companions), u.Gem.FreeGem, u.ImportantItems[100001])
	}
	if res.Gems != 500 {
		t.Fatalf("result gems %d", res.Gems)
	}
	m := u.MainQuest
	if m.HeadQuestSceneId != storyScene(31) || m.CurrentQuestSceneId != storyScene(31) || m.CurrentMainQuestRouteId != 4 || m.MainQuestSeasonId != 3 ||
		m.CurrentQuestFlowType != int32(model.QuestFlowTypeMainFlow) || m.IsReachedLastQuestScene {
		t.Fatalf("main quest %+v", m)
	}
	st := h.StoryStatusOf(u, p)
	if st.HeadQuestId != 31 || st.HeadChapterId != 5 || st.RouteId != 4 {
		t.Fatalf("status %+v", st)
	}
}

func TestJumpPaysOnce(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	clearQuest(u, 1)
	clearQuest(u, 2)
	u.MainQuest.HeadQuestSceneId = storyScene(3)
	res, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 10, Season2Route: 2}, 1000)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(res.Cleared, []int32{3}) {
		t.Fatalf("cleared %v", res.Cleared)
	}
	if u.ImportantItems[100001] != 0 || u.Quests[2].ClearCount != 1 {
		t.Fatalf("q2 paid again: item %d, clears %d", u.ImportantItems[100001], u.Quests[2].ClearCount)
	}
}

func TestJumpMidChapterKeepsEarlierClears(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	for _, q := range []int32{1, 2, 3} {
		clearQuest(u, q)
	}
	u.MainQuest.HeadQuestSceneId = storyScene(10)
	res, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 11, Season2Route: 2}, 1000)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(res.Cleared, []int32{10}) || u.MainQuest.HeadQuestSceneId != storyScene(11) {
		t.Fatalf("cleared %v, head %d", res.Cleared, u.MainQuest.HeadQuestSceneId)
	}
}

func TestJumpRefusesBehind(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	for _, q := range []int32{1, 2, 3, 10, 11} {
		clearQuest(u, q)
	}
	u.MainQuest.HeadQuestSceneId = storyScene(30)
	before := store.CloneUserState(*u)
	for _, target := range []int32{11, 30} {
		if _, err := h.JumpMainStory(u, p, StoryTarget{QuestId: target, Season2Route: 2}, 1000); !errors.Is(err, ErrStoryBehind) {
			t.Fatalf("target %d: err %v, want ErrStoryBehind", target, err)
		}
	}
	if !reflect.DeepEqual(before.Quests, u.Quests) || before.MainQuest != u.MainQuest {
		t.Fatal("a refused jump changed the save")
	}
}

func TestJumpRefusesOtherRoute(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	for _, q := range []int32{1, 2, 3, 20} {
		clearQuest(u, q)
	}
	u.MainQuest.HeadQuestSceneId = storyScene(30)
	u.MainQuest.CurrentMainQuestRouteId = 4
	if _, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 31, Season2Route: 2}, 1000); !errors.Is(err, ErrOtherRoute) {
		t.Fatalf("err %v, want ErrOtherRoute", err)
	}
	if _, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 31, Season2Route: 3}, 1000); err != nil {
		t.Fatalf("the save's own route: %v", err)
	}
}

func TestJumpBackgroundOpener(t *testing.T) {
	h, p := storyFixture()
	q := h.QuestById[10]
	q.IsRunInTheBackground = true
	h.QuestById[10] = q
	u := storyUser()
	if _, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 10, Season2Route: 2}, 1000); err != nil {
		t.Fatal(err)
	}
	if _, ok := u.Quests[10]; ok || u.MainQuest.HeadQuestSceneId != storyScene(10) {
		t.Fatalf("row %v, head %d", ok, u.MainQuest.HeadQuestSceneId)
	}
}

func TestJumpClearsSavedContext(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	u.MainQuest.SavedContext = store.SavedQuestContext{Active: true, HeadQuestSceneId: storyScene(1)}
	u.MainQuest.ProgressQuestSceneId = storyScene(1) + 1
	u.PortalCageStatus.IsCurrentProgress = true
	if _, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 3}, 1000); err != nil {
		t.Fatal(err)
	}
	if u.MainQuest.SavedContext != (store.SavedQuestContext{}) || u.MainQuest.ProgressQuestSceneId != 0 || u.PortalCageStatus.IsCurrentProgress {
		t.Fatalf("saved context %+v, progress %d, cage %v", u.MainQuest.SavedContext, u.MainQuest.ProgressQuestSceneId, u.PortalCageStatus.IsCurrentProgress)
	}
}

func TestJumpTutorials(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	if _, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 3}, 1000); err != nil {
		t.Fatal(err)
	}
	tut := u.Tutorials[int32(model.TutorialTypeCompanion)]
	if tut.ProgressPhase != 40 || tut.ChoiceId != 1 || len(u.Companions) != 1 {
		t.Fatalf("companion tutorial %+v, companions %d", tut, len(u.Companions))
	}
	if _, ok := u.Tutorials[9]; ok {
		t.Fatal("a menu tutorial (no scene) was marked done")
	}
	if _, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 10, Season2Route: 2}, 2000); err != nil {
		t.Fatal(err)
	}
	if len(u.Companions) != 2 { // q3's companion, and the tutorial's once
		t.Fatalf("%d companions after a second jump", len(u.Companions))
	}
}

func TestJumpNoOpening(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	delete(u.Costumes, "c1")
	if _, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 3}, 1000); !errors.Is(err, ErrNoOpening) {
		t.Fatalf("err %v", err)
	}
}

func TestJumpDryRunOnClone(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	c := store.CloneUserState(*u)
	res, err := h.JumpMainStory(&c, p, StoryTarget{QuestId: 3}, 1000)
	if err != nil || len(res.Cleared) != 2 {
		t.Fatalf("%v %v", res, err)
	}
	if len(u.Quests) != 0 || u.ImportantItems[100001] != 0 {
		t.Fatal("a jump on a clone changed the save")
	}
}

// A companion already chosen in the tutorial is kept: the jump finishes the
// tutorial without choosing again.
func TestJumpKeepsAChosenCompanion(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	u.Tutorials[int32(model.TutorialTypeCompanion)] = store.TutorialProgressState{TutorialType: int32(model.TutorialTypeCompanion), ProgressPhase: 30, ChoiceId: 3}
	if _, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 3}, 1000); err != nil {
		t.Fatal(err)
	}
	tut := u.Tutorials[int32(model.TutorialTypeCompanion)]
	if tut.ChoiceId != 3 || tut.ProgressPhase != 40 || len(u.Companions) != 0 {
		t.Fatalf("tutorial %+v, %d companions (the save's own choice must stand)", tut, len(u.Companions))
	}
}

// A quest left mid-replay (restarted from the quest menu, so Active, but
// cleared before) is not cleared again: its clear count stays and it isn't
// listed among the quests the jump cleared.
func TestJumpSkipsAQuestLeftMidReplay(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	clearQuest(u, 1)
	qs := u.Quests[1]
	qs.QuestStateType = model.UserQuestStateTypeActive
	u.Quests[1] = qs
	res, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 3}, 1000)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(res.Cleared, []int32{2}) || u.Quests[1].ClearCount != 1 {
		t.Fatalf("cleared %v, quest 1 clears %d", res.Cleared, u.Quests[1].ClearCount)
	}
}

// What the jump lists is what the save gains: a companion it already owns is
// not listed (the first-clear reward and the tutorial's).
func TestJumpListsOnlyNewCompanions(t *testing.T) {
	h, p := storyFixture()
	u := storyUser()
	u.Companions["a"] = store.CompanionState{UserCompanionUuid: "a", CompanionId: 7} // q3's reward
	u.Companions["b"] = store.CompanionState{UserCompanionUuid: "b", CompanionId: 2} // the tutorial's choice 1
	res, err := h.JumpMainStory(u, p, StoryTarget{QuestId: 10, Season2Route: 2}, 1000)
	if err != nil {
		t.Fatal(err)
	}
	for _, g := range res.Grants {
		if g.PossessionType == model.PossessionTypeCompanion {
			t.Fatalf("an owned companion was listed: %+v", g)
		}
	}
}
