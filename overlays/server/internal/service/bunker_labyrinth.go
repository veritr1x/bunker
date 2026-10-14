package service

import (
	"sync"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Labyrinth seasons. Each labyrinth (an event chapter) runs in seasons
// (m_event_quest_labyrinth_season). When a season ends, the player is paid the
// season reward for the furthest stage they reached; joining the next season
// starts the climb again: the labyrinth's quests and stage clear rewards
// reset, while the stage accumulation rewards (for quest missions cleared
// over time) are kept.

// labyrinthQuests are the quest ids of each labyrinth chapter.
var labyrinthQuests = sync.OnceValue(func() map[int32]map[int32]bool {
	sequences := map[int32][]int32{}
	for _, s := range table[masterdata.EntityMEventQuestSequence]("m_event_quest_sequence") {
		sequences[s.EventQuestSequenceId] = append(sequences[s.EventQuestSequenceId], s.QuestId)
	}
	groups := map[int32][]int32{}
	for _, g := range table[masterdata.EntityMEventQuestSequenceGroup]("m_event_quest_sequence_group") {
		groups[g.EventQuestSequenceGroupId] = append(groups[g.EventQuestSequenceGroupId], sequences[g.EventQuestSequenceId]...)
	}
	labyrinths := map[int32]bool{}
	for chapter := range labyrinthSeasons() {
		labyrinths[chapter] = true
	}
	out := map[int32]map[int32]bool{}
	for _, ch := range table[masterdata.EntityMEventQuestChapter]("m_event_quest_chapter") {
		if !labyrinths[ch.EventQuestChapterId] {
			continue
		}
		quests := map[int32]bool{}
		for _, q := range groups[ch.EventQuestSequenceGroupId] {
			quests[q] = true
		}
		out[ch.EventQuestChapterId] = quests
	}
	return out
})

// currentLabyrinthSeason is the chapter's open season at now (the latest
// started, if several are open), or 0.
func currentLabyrinthSeason(chapterId int32, now int64) int32 {
	current := int32(0)
	for _, s := range labyrinthSeasons()[chapterId] {
		if s.StartDatetime <= now && now <= s.EndDatetime && s.SeasonNumber > current {
			current = s.SeasonNumber
		}
	}
	return current
}

// settleLabyrinthSeason pays the season reward of the chapter's joined season
// once it has ended, for the furthest stage head quest cleared, and returns
// what was paid (nil if nothing was due).
func settleLabyrinthSeason(laby *masterdata.LabyrinthCatalog, granter *store.PossessionGranter, u *store.UserState, ch masterdata.LabyrinthChapter, now int64) *pb.LabyrinthSeasonResult {
	st, ok := u.LabyrinthSeasons[ch.EventQuestChapterId]
	if !ok {
		st = store.LabyrinthSeasonState{EventQuestChapterId: ch.EventQuestChapterId, LastJoinSeasonNumber: ch.LatestSeasonNumber}
	}
	if st.LastJoinSeasonNumber <= st.LastSeasonRewardReceivedSeasonNumber {
		return nil
	}
	ended := false
	for _, season := range labyrinthSeasons()[ch.EventQuestChapterId] {
		if season.SeasonNumber == st.LastJoinSeasonNumber && season.EndDatetime <= now {
			ended = true
		}
	}
	if !ended {
		return nil
	}
	var best *masterdata.LabyrinthSeasonMilestone
	milestones := laby.SeasonMilestones(ch.EventQuestChapterId)
	for i, m := range milestones {
		if u.Quests[m.HeadQuestId].ClearCount > 0 && (best == nil || m.HeadStageOrder > best.HeadStageOrder) {
			best = &milestones[i]
		}
	}
	st.LastSeasonRewardReceivedSeasonNumber = st.LastJoinSeasonNumber
	st.LatestVersion = now
	u.LabyrinthSeasons[ch.EventQuestChapterId] = st
	if best == nil {
		return nil
	}
	result := &pb.LabyrinthSeasonResult{EventQuestChapterId: ch.EventQuestChapterId, HeadQuestId: best.HeadQuestId, HeadStageOrder: best.HeadStageOrder}
	for _, it := range best.Rewards {
		granter.GrantFull(u, model.PossessionType(it.PossessionType), it.PossessionId, it.Count, now)
		result.SeasonReward = append(result.SeasonReward, &pb.LabyrinthReward{PossessionType: it.PossessionType, PossessionId: it.PossessionId, Count: it.Count})
	}
	return result
}

// joinLabyrinthSeason moves the player into the chapter's open season; a new
// season starts the labyrinth again. It reports whether the season changed.
func joinLabyrinthSeason(u *store.UserState, chapterId int32, now int64) bool {
	season := currentLabyrinthSeason(chapterId, now)
	st, ok := u.LabyrinthSeasons[chapterId]
	if season == 0 || (ok && st.LastJoinSeasonNumber == season) {
		return false
	}
	if ok && st.LastJoinSeasonNumber != 0 {
		quests := labyrinthQuests()[chapterId]
		for q := range quests {
			delete(u.Quests, q)
		}
		for k := range u.QuestMissions {
			if quests[k.QuestId] {
				delete(u.QuestMissions, k)
			}
		}
		if u.EventQuest.CurrentEventQuestChapterId == chapterId {
			u.EventQuest = store.EventQuestState{}
		}
		for k, stage := range u.LabyrinthStages {
			if k.EventQuestChapterId == chapterId && stage.IsReceivedStageClearReward {
				stage.IsReceivedStageClearReward = false
				stage.LatestVersion = now
				u.LabyrinthStages[k] = stage
			}
		}
	} else {
		// First visit: nothing earned before, so no reward is owed for an earlier season.
		st.LastSeasonRewardReceivedSeasonNumber = season - 1
	}
	st.EventQuestChapterId = chapterId
	st.LastJoinSeasonNumber = season
	st.LatestVersion = now
	u.LabyrinthSeasons[chapterId] = st
	return true
}
