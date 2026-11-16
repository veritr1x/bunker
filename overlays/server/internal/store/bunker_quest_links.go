package store

import (
	"sync/atomic"

	"lunar-tear/server/internal/model"
)

// Bunker: with the Original calendar, each earlier run of a rerun event plays
// its own copies of its quests (android_calendar.run_quest_copies), quest +
// (100 + n) * 10,000,000, so the game shows that run's drops. The live game's
// reruns replayed the same quests, and a clear carried over ("Quest clear
// status from previous runs will be carried over"): a quest and its copies
// share their progress. LinkQuests keeps them alike whenever a save is read or
// changed: each clear count, the daily count, the last and fastest clear, the
// first-clear reward and the quest missions; a quest in play keeps its own
// state, deck and start time.

const (
	questCopyStep = 10_000_000
	questCopyBase = 100 * questCopyStep // scene ids reach 999,012,001; quest copies start above
)

// OriginalQuest is the quest a copy was made from (the quest itself otherwise).
func OriginalQuest(id int32) int32 {
	if IsQuestCopy(id) {
		return id % questCopyStep
	}
	return id
}

// IsQuestCopy tells an earlier run's copy of a quest.
func IsQuestCopy(id int32) bool { return id >= questCopyBase }

var questCopies atomic.Pointer[map[int32][]int32] // original -> its copies in the game data

// SetQuestCopies records the copies among the game data's quests (runtime.Holder, on each load).
func SetQuestCopies(questIds []int32) {
	families := map[int32][]int32{}
	for _, id := range questIds {
		if IsQuestCopy(id) {
			families[OriginalQuest(id)] = append(families[OriginalQuest(id)], id)
		}
	}
	questCopies.Store(&families)
}

// QuestFamily is a quest with its copies (the quest alone when it has none).
func QuestFamily(id int32) []int32 {
	original := OriginalQuest(id)
	if p := questCopies.Load(); p != nil {
		if copies, ok := (*p)[original]; ok {
			return append([]int32{original}, copies...)
		}
	}
	return []int32{id}
}

// LinkQuests gives a quest and its copies the same progress.
func LinkQuests(u *UserState) {
	p := questCopies.Load()
	if p == nil || len(*p) == 0 || u.Quests == nil {
		return
	}
	for original, copies := range *p {
		members := append([]int32{original}, copies...)
		linkQuestStates(u, members)
		linkQuestMissions(u, members)
	}
}

func linkQuestStates(u *UserState, members []int32) {
	var shared UserQuestState
	present, cleared, challenged := false, false, false
	for _, id := range members {
		q, ok := u.Quests[id]
		if !ok {
			continue
		}
		present = true
		shared.ClearCount = max(shared.ClearCount, q.ClearCount)
		shared.DailyClearCount = max(shared.DailyClearCount, q.DailyClearCount)
		shared.LastClearDatetime = max(shared.LastClearDatetime, q.LastClearDatetime)
		if q.ShortestClearFrames > 0 && (shared.ShortestClearFrames == 0 || q.ShortestClearFrames < shared.ShortestClearFrames) {
			shared.ShortestClearFrames = q.ShortestClearFrames
		}
		shared.IsRewardGranted = shared.IsRewardGranted || q.IsRewardGranted
		cleared = cleared || q.QuestStateType == model.UserQuestStateTypeCleared || q.ClearCount > 0
		challenged = challenged || q.QuestStateType == model.UserQuestStateTypeChallenged
	}
	if !present || (!cleared && !challenged) {
		return // nothing to carry over: a quest only started stays the one it is
	}
	for _, id := range members {
		q, ok := u.Quests[id]
		if !ok {
			q = UserQuestState{QuestId: id}
		}
		next := q
		next.ClearCount, next.DailyClearCount, next.LastClearDatetime = shared.ClearCount, shared.DailyClearCount, shared.LastClearDatetime
		next.ShortestClearFrames, next.IsRewardGranted = shared.ShortestClearFrames, shared.IsRewardGranted
		if q.QuestStateType != model.UserQuestStateTypeActive {
			if cleared {
				next.QuestStateType = model.UserQuestStateTypeCleared
			} else {
				next.QuestStateType = model.UserQuestStateTypeChallenged
			}
		}
		if !ok || next != q {
			u.Quests[id] = next
		}
	}
}

func linkQuestMissions(u *UserState, members []int32) {
	if u.QuestMissions == nil {
		return
	}
	in := map[int32]bool{}
	for _, id := range members {
		in[id] = true
	}
	shared := map[int32]UserQuestMissionState{}
	for k, m := range u.QuestMissions {
		if !in[k.QuestId] {
			continue
		}
		s, seen := shared[k.QuestMissionId]
		if !seen {
			s = UserQuestMissionState{QuestMissionId: k.QuestMissionId}
		}
		s.ProgressValue = max(s.ProgressValue, m.ProgressValue)
		s.IsClear = s.IsClear || m.IsClear
		s.LatestClearDatetime = max(s.LatestClearDatetime, m.LatestClearDatetime)
		shared[k.QuestMissionId] = s
	}
	for mission, s := range shared {
		for _, id := range members {
			if _, played := u.Quests[id]; !played {
				continue
			}
			k := QuestMissionKey{QuestId: id, QuestMissionId: mission}
			m, ok := u.QuestMissions[k]
			next := m
			next.QuestId, next.QuestMissionId = id, mission
			next.ProgressValue, next.IsClear, next.LatestClearDatetime = s.ProgressValue, s.IsClear, s.LatestClearDatetime
			if !ok || next != m {
				u.QuestMissions[k] = next
			}
		}
	}
}
