package questflow

import (
	"errors"
	"fmt"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Bunker: Pod Programs › Story Jump. Brings a save forward to the start of a
// main-story quest: every main-flow quest before it is cleared the way the
// server clears a quest the story moves past (finalizeChainPreviousQuest:
// exp, gold and first-clear items once, missions marked clear without their
// rewards, no drops), the scene-gated tutorials before it are finished, and
// the story pointer is put on the quest's first scene. Forward only.

type StoryTarget struct {
	QuestId      int32
	Season2Route int32 // 2 or 3; 0 picks the save's own season-2 route, else 2
}

type StoryStatus struct {
	RouteId, SeasonId, HeadQuestId, HeadChapterId int32
	Cleared                                       []int32 // main-flow quests cleared at least once
}

type JumpResult struct {
	Cleared []int32       // quests this jump cleared, in order
	Grants  []RewardGrant // items given (first clears, starter grants, companion), gems excluded
	Gems    int32
}

var (
	ErrStoryBehind = errors.New("the save is already at or past that point")
	ErrOtherRoute  = errors.New("the save is on the other season-2 route")
	ErrNoOpening   = errors.New("play the game's opening first")
)

// The phase each scene-gated tutorial ends on, from a save that played past
// them; others end on 10.
var storyTutorialFinished = map[int32]int32{2: 20, 3: 30, 4: 10, 5: 10, 6: 10, 8: 40, 25: 50}

const starterScene = 2 // MUserQuestSceneGrantPossession: the starter costume and weapons

func (h *QuestHandler) StoryStatusOf(user *store.UserState, p *masterdata.StoryPath) StoryStatus {
	head := p.SceneQuest[user.MainQuest.HeadQuestSceneId]
	st := StoryStatus{
		RouteId:       user.MainQuest.CurrentMainQuestRouteId,
		SeasonId:      user.MainQuest.MainQuestSeasonId,
		HeadQuestId:   head,
		HeadChapterId: p.ChapterOf[head],
	}
	for _, route := range []int32{1, 2, 3, 4} {
		for _, c := range p.Chapters[route] {
			for _, q := range c.QuestIds {
				if user.Quests[q].ClearCount > 0 {
					st.Cleared = append(st.Cleared, q)
				}
			}
		}
	}
	return st
}

// season2RouteOf is the season-2 route the save has taken: its head's, or
// the one with a cleared quest; 0 if none.
func season2RouteOf(user *store.UserState, p *masterdata.StoryPath) int32 {
	head := p.SceneQuest[user.MainQuest.HeadQuestSceneId]
	if p.SeasonOf(head) == 2 {
		return p.RouteOf[head]
	}
	for _, r := range p.Seasons[2] {
		for _, c := range p.Chapters[r] {
			for _, q := range c.QuestIds {
				if user.Quests[q].ClearCount > 0 {
					return r
				}
			}
		}
	}
	return 0
}

// owns: a costume or companion the save already has (a second copy isn't
// added; the game exchanges it instead).
func owns(user *store.UserState, possType model.PossessionType, id int32) bool {
	switch possType {
	case model.PossessionTypeCostume:
		for _, c := range user.Costumes {
			if c.CostumeId == id {
				return true
			}
		}
	case model.PossessionTypeCompanion:
		for _, c := range user.Companions {
			if c.CompanionId == id {
				return true
			}
		}
	}
	return false
}

func (h *QuestHandler) JumpMainStory(user *store.UserState, p *masterdata.StoryPath, t StoryTarget, nowMillis int64) (JumpResult, error) {
	var res JumpResult
	if len(user.Costumes) == 0 {
		return res, ErrNoOpening
	}
	targetSeason := p.SeasonOf(t.QuestId)
	if targetSeason == 0 {
		return res, fmt.Errorf("quest %d is not a main-story quest", t.QuestId)
	}
	taken := season2RouteOf(user, p)
	route := t.Season2Route
	if route == 0 {
		switch {
		case targetSeason == 2:
			route = p.RouteOf[t.QuestId]
		case taken != 0:
			route = taken
		default:
			route = 2
		}
	}
	path, err := p.Path(t.QuestId, route)
	if err != nil {
		return res, err
	}
	if targetSeason >= 2 && taken != 0 && taken != route {
		return res, ErrOtherRoute
	}
	targetScene := p.FirstScene[t.QuestId]
	head := p.SceneQuest[user.MainQuest.HeadQuestSceneId]
	if user.Quests[t.QuestId].ClearCount > 0 || head == t.QuestId ||
		(head != 0 && (p.SeasonOf(head) > targetSeason ||
			(p.RouteOf[head] == p.RouteOf[t.QuestId] && p.SceneOrder[user.MainQuest.HeadQuestSceneId] > p.SceneOrder[targetScene]))) {
		return res, ErrStoryBehind
	}

	given := map[[2]int32]int32{}
	var order [][2]int32
	give := func(possType model.PossessionType, id, count int32) {
		if possType == model.PossessionTypeFreeGem || possType == model.PossessionTypePaidGem {
			res.Gems += count
			return
		}
		if owns(user, possType, id) { // listed only if the save gains it
			return
		}
		k := [2]int32{int32(possType), id}
		if _, ok := given[k]; !ok {
			order = append(order, k)
		}
		given[k] += count
	}

	if h.isSceneAhead(starterScene, user.MainQuest.HeadQuestSceneId) {
		for _, g := range h.SceneGrantsBySceneId[starterScene] {
			give(model.PossessionType(g.PossessionType), g.PossessionId, g.Count)
		}
		h.applySceneGrants(user, starterScene, nowMillis)
	}

	for _, q := range path {
		// Cleared before (a quest restarted from the quest menu is Active
		// again but keeps its clears): left as it is.
		if qs := user.Quests[q]; qs.QuestStateType == model.UserQuestStateTypeCleared || qs.ClearCount > 0 {
			continue
		}
		def, ok := h.QuestById[q]
		if !ok {
			continue
		}
		if !user.Quests[q].IsRewardGranted {
			for _, r := range h.FirstClearRewardsByGroupId[h.firstClearRewardGroupId(user, def)] {
				give(model.PossessionType(r.PossessionType), r.PossessionId, r.Count)
			}
		}
		h.grantWeaponStoryUnlocksForQuestScene(user, q, model.QuestResultTypeHalfResult, nowMillis)
		h.finalizeChainPreviousQuest(user, q, nowMillis)
		h.grantWeaponStoryUnlocksForQuestScene(user, q, model.QuestResultTypeFullResult, nowMillis)
		res.Cleared = append(res.Cleared, q)
	}

	for _, c := range h.TutorialUnlockConditions {
		ct := model.TutorialUnlockConditionType(c.TutorialUnlockConditionType)
		if ct != model.TutorialUnlockConditionTypeReachSpecifiedQuestScene && ct != model.TutorialUnlockConditionTypeUntilReachSpecifiedScene {
			continue
		}
		order, ok := p.SceneOrder[c.ConditionValue]
		if !ok || order >= p.SceneOrder[targetScene] {
			continue
		}
		finished, ok := storyTutorialFinished[c.TutorialType]
		if !ok {
			finished = 10
		}
		cur := user.Tutorials[c.TutorialType]
		if cur.ProgressPhase >= finished {
			continue
		}
		cur.TutorialType, cur.ProgressPhase, cur.LatestVersion = c.TutorialType, finished, nowMillis
		switch model.TutorialType(c.TutorialType) {
		case model.TutorialTypeCompanion:
			if cur.ChoiceId != 0 { // chosen already in the game: that choice stands
				break
			}
			cur.ChoiceId = 1
			had := owns(user, model.PossessionTypeCompanion, tutorialCompanionChoices[1])
			for _, g := range h.ApplyTutorialReward(user, model.TutorialTypeCompanion, 1, nowMillis) {
				if !had {
					give(g.PossessionType, g.PossessionId, g.Count)
				}
			}
		case model.TutorialTypeMenuFirst:
			defer store.EnsureDefaultDeck(user, nowMillis)
		}
		user.Tutorials[c.TutorialType] = cur
	}

	m := &user.MainQuest
	m.CurrentQuestFlowType = int32(model.QuestFlowTypeMainFlow)
	m.CurrentMainQuestRouteId = p.RouteOf[t.QuestId]
	m.MainQuestSeasonId = targetSeason
	m.CurrentQuestSceneId = targetScene
	m.HeadQuestSceneId = targetScene
	m.IsReachedLastQuestScene = false
	m.ProgressQuestSceneId, m.ProgressHeadQuestSceneId, m.ProgressQuestFlowType = 0, 0, 0
	m.SavedContext = store.SavedQuestContext{}
	m.LatestVersion = nowMillis
	if user.SideStoryActiveProgress.CurrentSideStoryQuestId != 0 {
		user.SideStoryActiveProgress = store.SideStoryActiveProgress{LatestVersion: nowMillis}
	}
	user.PortalCageStatus.IsCurrentProgress = false
	user.PortalCageStatus.LatestVersion = nowMillis

	for _, k := range order {
		res.Grants = append(res.Grants, RewardGrant{PossessionType: model.PossessionType(k[0]), PossessionId: k[1], Count: given[k]})
	}
	return res, nil
}
