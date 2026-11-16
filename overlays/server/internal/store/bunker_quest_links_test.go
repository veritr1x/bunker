package store

import (
	"testing"

	"lunar-tear/server/internal/model"
)

const runCopy = 100 * questCopyStep // an earlier run's copy: quest + (100 + n) * 10,000,000

func linkedUser(quests map[int32]UserQuestState) *UserState {
	u := &UserState{Quests: quests, QuestMissions: map[QuestMissionKey]UserQuestMissionState{}}
	return u
}

func TestQuestCopiesAreKnownByTheirIds(t *testing.T) {
	if OriginalQuest(200583+runCopy) != 200583 || OriginalQuest(200583+runCopy+questCopyStep) != 200583 || OriginalQuest(200583) != 200583 {
		t.Fatal("a copy's original is its id modulo the copy step")
	}
	if !IsQuestCopy(200583+runCopy) || IsQuestCopy(200583) || IsQuestCopy(999012001) {
		t.Fatal("only ids from 1,000,000,000 are copies (scene ids reach 999,012,001)")
	}
}

// The live game's reruns replayed the same quests: a clear in one run is a
// clear in the others (the rerun notices: "Quest clear status from previous
// runs will be carried over").
func TestAClearInOneRunIsAClearInTheOthers(t *testing.T) {
	SetQuestCopies([]int32{1, 2, 1 + runCopy, 2 + runCopy, 2 + runCopy + questCopyStep, 3})
	defer SetQuestCopies(nil)

	// An existing save cleared the originals before copies existed: its copies show them cleared.
	u := linkedUser(map[int32]UserQuestState{1: {QuestId: 1, QuestStateType: model.UserQuestStateTypeCleared, ClearCount: 3,
		LastClearDatetime: 50, ShortestClearFrames: 900, IsRewardGranted: true, UserDeckNumber: 2}})
	LinkQuests(u)
	c := u.Quests[1+runCopy]
	if c.QuestId != 1+runCopy || c.QuestStateType != model.UserQuestStateTypeCleared || c.ClearCount != 3 || !c.IsRewardGranted ||
		c.LastClearDatetime != 50 || c.ShortestClearFrames != 900 {
		t.Fatalf("copy %+v", c)
	}
	if _, ok := u.Quests[2+runCopy]; ok {
		t.Fatal("a quest no run has played gets no row")
	}

	// Clearing a copy counts for the original and the other runs, once.
	u = linkedUser(map[int32]UserQuestState{2 + runCopy: {QuestId: 2 + runCopy, QuestStateType: model.UserQuestStateTypeCleared, ClearCount: 1,
		DailyClearCount: 1, LastClearDatetime: 70, ShortestClearFrames: 600, IsRewardGranted: true}})
	LinkQuests(u)
	for _, id := range []int32{2, 2 + runCopy + questCopyStep} {
		if q := u.Quests[id]; q.ClearCount != 1 || q.DailyClearCount != 1 || q.QuestStateType != model.UserQuestStateTypeCleared || !q.IsRewardGranted {
			t.Fatalf("quest %d: %+v", id, q)
		}
	}
	LinkQuests(u)
	if u.Quests[2].ClearCount != 1 {
		t.Fatal("linking again adds nothing")
	}
}

func TestAQuestInPlayKeepsItsOwnState(t *testing.T) {
	SetQuestCopies([]int32{1, 1 + runCopy})
	defer SetQuestCopies(nil)
	u := linkedUser(map[int32]UserQuestState{
		1:           {QuestId: 1, QuestStateType: model.UserQuestStateTypeCleared, ClearCount: 2, LastClearDatetime: 40, ShortestClearFrames: 800},
		1 + runCopy: {QuestId: 1 + runCopy, QuestStateType: model.UserQuestStateTypeActive, LatestStartDatetime: 99, UserDeckNumber: 3},
	})
	LinkQuests(u)
	c := u.Quests[1+runCopy]
	if c.QuestStateType != model.UserQuestStateTypeActive || c.LatestStartDatetime != 99 || c.UserDeckNumber != 3 || c.ClearCount != 2 {
		t.Fatalf("the copy in play: %+v", c)
	}
	if o := u.Quests[1]; o.QuestStateType != model.UserQuestStateTypeCleared || o.LatestStartDatetime != 0 {
		t.Fatalf("the original: %+v", o)
	}
}

func TestQuestMissionsAreSharedToo(t *testing.T) {
	SetQuestCopies([]int32{1, 1 + runCopy})
	defer SetQuestCopies(nil)
	u := linkedUser(map[int32]UserQuestState{1: {QuestId: 1, QuestStateType: model.UserQuestStateTypeCleared, ClearCount: 1}})
	u.QuestMissions[QuestMissionKey{QuestId: 1 + runCopy, QuestMissionId: 7}] = UserQuestMissionState{QuestId: 1 + runCopy, QuestMissionId: 7,
		ProgressValue: 1, IsClear: true, LatestClearDatetime: 30}
	u.QuestMissions[QuestMissionKey{QuestId: 1, QuestMissionId: 8}] = UserQuestMissionState{QuestId: 1, QuestMissionId: 8, ProgressValue: 0}
	LinkQuests(u)
	if m := u.QuestMissions[QuestMissionKey{QuestId: 1, QuestMissionId: 7}]; !m.IsClear || m.QuestId != 1 || m.LatestClearDatetime != 30 {
		t.Fatalf("original's mission 7: %+v", m)
	}
	if m, ok := u.QuestMissions[QuestMissionKey{QuestId: 1 + runCopy, QuestMissionId: 8}]; !ok || m.IsClear || m.QuestId != 1+runCopy {
		t.Fatalf("copy's mission 8: %+v %v", m, ok)
	}
}

func TestWithoutCopiesNothingChanges(t *testing.T) {
	SetQuestCopies(nil)
	u := linkedUser(map[int32]UserQuestState{1: {QuestId: 1, ClearCount: 1}})
	LinkQuests(u)
	if len(u.Quests) != 1 {
		t.Fatal("rows added without copies")
	}
}
