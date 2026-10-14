package service

import (
	"context"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/store"
)

func TestLabyrinthSeasonsMoveOn(t *testing.T) {
	holder, users := harness(t)
	laby := holder.Get().Labyrinth
	srv := NewLabyrinthServiceServer(users, users, holder)
	ctx := context.Background()
	const chapter = 801
	seasons := labyrinthSeasons()[chapter]
	if len(seasons) < 2 {
		t.Fatal("labyrinth 801 needs two seasons")
	}
	s1, s2 := seasons[0], seasons[1]
	milestones := laby.SeasonMilestones(chapter)
	if len(milestones) == 0 {
		t.Fatal("no season milestones")
	}

	// Season 1: joining pays nothing.
	setClock(t, s1.StartDatetime+1000)
	resp, err := srv.UpdateSeasonData(ctx, &pb.UpdateSeasonDataRequest{EventQuestChapterId: chapter})
	if err != nil || len(resp.SeasonResult) != 0 || users.user.LabyrinthSeasons[chapter].LastJoinSeasonNumber != s1.SeasonNumber {
		t.Fatalf("join season 1: %v %v %+v", resp, err, users.user.LabyrinthSeasons[chapter])
	}
	// The player climbs: the first milestone's head quest is cleared, a stage clear reward taken.
	head := milestones[0].HeadQuestId
	users.user.Quests[head] = store.UserQuestState{QuestId: head, ClearCount: 1}
	stage := store.LabyrinthStageKey{EventQuestChapterId: chapter, StageOrder: 1}
	users.user.LabyrinthStages[stage] = store.LabyrinthStageState{EventQuestChapterId: chapter, StageOrder: 1, IsReceivedStageClearReward: true, AccumulationRewardReceivedQuestMissionCount: 3}

	// Season 2: season 1's reward is paid once, and the climb starts again.
	setClock(t, s2.StartDatetime+1000)
	resp, err = srv.UpdateSeasonData(ctx, &pb.UpdateSeasonDataRequest{EventQuestChapterId: chapter})
	if err != nil || len(resp.SeasonResult) != 1 || resp.SeasonResult[0].HeadQuestId != head || len(resp.SeasonResult[0].SeasonReward) == 0 {
		t.Fatalf("season 1 reward: %v %v", resp, err)
	}
	st := users.user.LabyrinthSeasons[chapter]
	if st.LastJoinSeasonNumber != s2.SeasonNumber || st.LastSeasonRewardReceivedSeasonNumber != s1.SeasonNumber {
		t.Fatalf("season state %+v", st)
	}
	if users.user.Quests[head].ClearCount != 0 {
		t.Fatal("labyrinth quests not reset for the new season")
	}
	if s := users.user.LabyrinthStages[stage]; s.IsReceivedStageClearReward || s.AccumulationRewardReceivedQuestMissionCount != 3 {
		t.Fatalf("stage state after reset: %+v", s)
	}
	resp, _ = srv.UpdateSeasonData(ctx, &pb.UpdateSeasonDataRequest{EventQuestChapterId: chapter})
	if len(resp.SeasonResult) != 0 {
		t.Fatal("season 1 reward paid twice")
	}
}
