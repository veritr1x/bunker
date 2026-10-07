package service

// Handlers Bunker adds to Lunar Tear: mission and mission pass rewards, skipping
// several quests at once, the daily quest set reward, costume level bonus
// confirmation, story choices, labyrinth season rewards and two empty lists the
// game asks for.

import (
	"context"
	"log"
	"math/rand"
	"sort"
	"sync"
	"time"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/missions"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/pvp"
	"lunar-tear/server/internal/questflow"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"

	emptypb "google.golang.org/protobuf/types/known/emptypb"
)

var bunkerHolder *runtime.Holder

// InitBunker gives Bunker's handlers and the mission tracker the master data
// (MissionService has no holder of its own).
func InitBunker(h *runtime.Holder) {
	bunkerHolder = h
	missions.SetHolder(h)
	pvp.SetHolder(h)
	missions.GachaLabel = func(gachaId int32) int32 {
		for _, e := range h.Get().GachaEntries {
			if e.GachaId == gachaId {
				return e.GachaLabelType
			}
		}
		return 0
	}
}

func missionRewards(rs []missions.Reward) []*pb.MissionReward {
	out := make([]*pb.MissionReward, 0, len(rs))
	for _, r := range rs {
		out = append(out, &pb.MissionReward{PossessionType: r.PossessionType, PossessionId: r.PossessionId, Count: r.Count})
	}
	return out
}

func (s *MissionServiceServer) ReceiveMissionRewardsById(ctx context.Context, req *pb.ReceiveMissionRewardsByIdRequest) (*pb.ReceiveMissionRewardsResponse, error) {
	log.Printf("[MissionService] ReceiveMissionRewardsById: %v", req.MissionId)
	cat := missions.Current()
	var received []missions.Reward
	if cat != nil && bunkerHolder != nil {
		granter := bunkerHolder.Get().QuestHandler.Granter
		userId := CurrentUserId(ctx, s.users, s.sessions)
		if _, err := s.users.UpdateUser(userId, func(u *store.UserState) {
			received = cat.ReceiveMissions(u, granter, req.MissionId, gametime.NowMillis())
		}); err != nil {
			return nil, err
		}
	}
	return &pb.ReceiveMissionRewardsResponse{
		ReceivedPossession: missionRewards(received),
		ExpiredPossession:  []*pb.MissionReward{},
		OverflowPossession: []*pb.MissionReward{},
	}, nil
}

func (s *MissionServiceServer) ReceiveMissionPassRewards(ctx context.Context, req *pb.ReceiveMissionPassRewardsRequest) (*pb.ReceiveMissionPassRewardsResponse, error) {
	log.Printf("[MissionService] ReceiveMissionPassRewards: pass=%d", req.MissionPassId)
	cat := missions.Current()
	var received []missions.Reward
	if cat != nil && bunkerHolder != nil {
		granter := bunkerHolder.Get().QuestHandler.Granter
		userId := CurrentUserId(ctx, s.users, s.sessions)
		if _, err := s.users.UpdateUser(userId, func(u *store.UserState) {
			received = cat.ReceivePass(u, granter, req.MissionPassId, gametime.NowMillis())
		}); err != nil {
			return nil, err
		}
	}
	out := make([]*pb.MissionPassReward, 0, len(received))
	for _, r := range received {
		out = append(out, &pb.MissionPassReward{PossessionType: r.PossessionType, PossessionId: r.PossessionId, Count: r.Count})
	}
	return &pb.ReceiveMissionPassRewardsResponse{ReceivedPossession: out, OverflowPossession: []*pb.MissionPassReward{}}, nil
}

func (s *RewardServiceServer) ReceiveMissionPassRemainingReward(ctx context.Context, _ *emptypb.Empty) (*pb.ReceiveMissionPassRemainingRewardResponse, error) {
	cat := missions.Current()
	var passId int32
	if cat != nil {
		granter := s.holder.Get().QuestHandler.Granter
		userId := CurrentUserId(ctx, s.users, s.sessions)
		if _, err := s.users.UpdateUser(userId, func(u *store.UserState) {
			passId = cat.ReceiveEndedPasses(u, granter, gametime.NowMillis())
		}); err != nil {
			return nil, err
		}
	}
	log.Printf("[RewardService] ReceiveMissionPassRemainingReward: pass=%d", passId)
	return &pb.ReceiveMissionPassRemainingRewardResponse{RewardReceivedMissionPassId: passId}, nil
}

var labyrinthSeasons = sync.OnceValue(func() map[int32][]masterdata.EntityMEventQuestLabyrinthSeason {
	rows, err := utils.ReadTable[masterdata.EntityMEventQuestLabyrinthSeason]("m_event_quest_labyrinth_season")
	if err != nil {
		log.Printf("[RewardService] m_event_quest_labyrinth_season: %v", err)
	}
	out := map[int32][]masterdata.EntityMEventQuestLabyrinthSeason{}
	for _, r := range rows {
		out[r.EventQuestChapterId] = append(out[r.EventQuestChapterId], r)
	}
	return out
})

// ReceiveLabyrinthSeasonReward pays, for each labyrinth whose joined season has
// ended, the season reward for the furthest stage head quest the player cleared.
func (s *RewardServiceServer) ReceiveLabyrinthSeasonReward(ctx context.Context, _ *emptypb.Empty) (*pb.ReceiveLabyrinthSeasonRewardResponse, error) {
	cats := s.holder.Get()
	laby := cats.Labyrinth
	granter := cats.QuestHandler.Granter
	now := gametime.NowMillis()
	userId := CurrentUserId(ctx, s.users, s.sessions)
	var results []*pb.LabyrinthSeasonResult
	_, err := s.users.UpdateUser(userId, func(u *store.UserState) {
		for _, ch := range laby.ChaptersByOrder {
			st, ok := u.LabyrinthSeasons[ch.EventQuestChapterId]
			if !ok {
				st = store.LabyrinthSeasonState{EventQuestChapterId: ch.EventQuestChapterId, LastJoinSeasonNumber: ch.LatestSeasonNumber}
			}
			if st.LastJoinSeasonNumber <= st.LastSeasonRewardReceivedSeasonNumber {
				continue
			}
			ended := false
			for _, season := range labyrinthSeasons()[ch.EventQuestChapterId] {
				if season.SeasonNumber == st.LastJoinSeasonNumber && season.EndDatetime <= now {
					ended = true
				}
			}
			if !ended {
				continue
			}
			var best *masterdata.LabyrinthSeasonMilestone
			for i, m := range laby.SeasonMilestones(ch.EventQuestChapterId) {
				if u.Quests[m.HeadQuestId].ClearCount > 0 && (best == nil || m.HeadStageOrder > best.HeadStageOrder) {
					best = &laby.SeasonMilestones(ch.EventQuestChapterId)[i]
				}
			}
			st.LastSeasonRewardReceivedSeasonNumber = st.LastJoinSeasonNumber
			st.LatestVersion = now
			u.LabyrinthSeasons[ch.EventQuestChapterId] = st
			if best == nil {
				continue
			}
			result := &pb.LabyrinthSeasonResult{EventQuestChapterId: ch.EventQuestChapterId, HeadQuestId: best.HeadQuestId, HeadStageOrder: best.HeadStageOrder}
			for _, it := range best.Rewards {
				granter.GrantFull(u, model.PossessionType(it.PossessionType), it.PossessionId, it.Count, now)
				result.SeasonReward = append(result.SeasonReward, &pb.LabyrinthReward{PossessionType: it.PossessionType, PossessionId: it.PossessionId, Count: it.Count})
			}
			results = append(results, result)
		}
	})
	if err != nil {
		return nil, err
	}
	log.Printf("[RewardService] ReceiveLabyrinthSeasonReward: %d season reward(s)", len(results))
	return &pb.ReceiveLabyrinthSeasonRewardResponse{SeasonResult: results}, nil
}

// SkipQuestBulk skips several quests in one go, as SkipQuest does for one.
func (s *QuestServiceServer) SkipQuestBulk(ctx context.Context, req *pb.SkipQuestBulkRequest) (*pb.SkipQuestBulkResponse, error) {
	log.Printf("[QuestService] SkipQuestBulk: %d quest(s) deck=%d", len(req.SkipQuestInfo), req.UserDeckNumber)
	nowMillis := gametime.NowMillis()
	engine := s.holder.Get().QuestHandler
	userId := CurrentUserId(ctx, s.users, s.sessions)
	var drops []questflow.RewardGrant
	if _, err := s.users.UpdateUser(userId, func(user *store.UserState) {
		for _, item := range req.UseEffectItem {
			user.ConsumableItems[item.ConsumableItemId] = max(0, user.ConsumableItems[item.ConsumableItemId]-item.Count)
		}
		for _, info := range req.SkipQuestInfo {
			outcome := engine.HandleQuestSkip(user, info.QuestId, info.SkipCount, nowMillis)
			drops = append(drops, outcome.DropRewards...)
		}
	}); err != nil {
		return nil, err
	}
	return &pb.SkipQuestBulkResponse{DropReward: toProtoRewards(drops), UserStatusCampaignReward: []*pb.QuestReward{}}, nil
}

type dailyGroupTables struct {
	groups  []masterdata.EntityMEventQuestDailyGroup
	rewards map[int32][]masterdata.EntityMEventQuestDailyGroupCompleteReward
}

var dailyGroups = sync.OnceValue(func() dailyGroupTables {
	t := dailyGroupTables{rewards: map[int32][]masterdata.EntityMEventQuestDailyGroupCompleteReward{}}
	var err error
	if t.groups, err = utils.ReadTable[masterdata.EntityMEventQuestDailyGroup]("m_event_quest_daily_group"); err != nil {
		log.Printf("[QuestService] m_event_quest_daily_group: %v", err)
	}
	rewards, err := utils.ReadTable[masterdata.EntityMEventQuestDailyGroupCompleteReward]("m_event_quest_daily_group_complete_reward")
	if err != nil {
		log.Printf("[QuestService] m_event_quest_daily_group_complete_reward: %v", err)
	}
	for _, r := range rewards {
		t.rewards[r.EventQuestDailyGroupCompleteRewardId] = append(t.rewards[r.EventQuestDailyGroupCompleteRewardId], r)
	}
	for id := range t.rewards {
		sort.Slice(t.rewards[id], func(i, j int) bool { return t.rewards[id][i].SortOrder < t.rewards[id][j].SortOrder })
	}
	return t
})

// ReceiveDailyQuestGroupCompleteReward pays the daily quest set's reward once a
// day. The game asks for it after the set is complete; the set in force is the
// open one that started last.
func (s *QuestServiceServer) ReceiveDailyQuestGroupCompleteReward(ctx context.Context, _ *emptypb.Empty) (*pb.ReceiveDailyQuestGroupCompleteRewardResponse, error) {
	now := gametime.NowMillis()
	t := time.UnixMilli(now).UTC()
	today := time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, time.UTC).UnixMilli()
	var group *masterdata.EntityMEventQuestDailyGroup
	for i, g := range dailyGroups().groups {
		if g.StartDatetime <= now && now < g.EndDatetime && (group == nil || g.StartDatetime > group.StartDatetime) {
			group = &dailyGroups().groups[i]
		}
	}
	if group == nil {
		log.Printf("[QuestService] ReceiveDailyQuestGroupCompleteReward: no daily quest set open")
		return &pb.ReceiveDailyQuestGroupCompleteRewardResponse{}, nil
	}
	granter := s.holder.Get().QuestHandler.Granter
	userId := CurrentUserId(ctx, s.users, s.sessions)
	paid := 0
	if _, err := s.users.UpdateUser(userId, func(u *store.UserState) {
		if u.Ext.DailyGroupReward.LastRewardReceiveDatetime >= today {
			return
		}
		for _, r := range dailyGroups().rewards[group.EventQuestDailyGroupCompleteRewardId] {
			granter.GrantFull(u, model.PossessionType(r.PossessionType), r.PossessionId, r.Count, now)
			paid++
		}
		u.Ext.DailyGroupReward = store.DailyGroupRewardState{
			LastRewardReceiveEventQuestDailyGroupId: group.EventQuestDailyGroupId,
			LastRewardReceiveDatetime:               now,
			LatestVersion:                           now,
		}
	}); err != nil {
		return nil, err
	}
	log.Printf("[QuestService] ReceiveDailyQuestGroupCompleteReward: set=%d paid %d item(s)", group.EventQuestDailyGroupId, paid)
	return &pb.ReceiveDailyQuestGroupCompleteRewardResponse{}, nil
}

// RegisterLevelBonusConfirmed records that the player has seen a costume's level bonus.
func (s *CostumeServiceServer) RegisterLevelBonusConfirmed(ctx context.Context, req *pb.RegisterLevelBonusConfirmedRequest) (*pb.RegisterLevelBonusConfirmedResponse, error) {
	log.Printf("[CostumeService] RegisterLevelBonusConfirmed: costume=%d level=%d", req.CostumeId, req.Level)
	userId := CurrentUserId(ctx, s.users, s.sessions)
	if _, err := s.users.UpdateUser(userId, func(u *store.UserState) {
		u.Ext.EnsureMaps()
		u.Ext.LevelBonusConfirmed[req.CostumeId] = max(u.Ext.LevelBonusConfirmed[req.CostumeId], req.Level)
	}); err != nil {
		return nil, err
	}
	return &pb.RegisterLevelBonusConfirmedResponse{}, nil
}

type sceneChoiceKey struct{ sceneId, flowType, choice int32 }

var sceneChoices = sync.OnceValue(func() map[sceneChoiceKey]masterdata.EntityMQuestSceneChoiceEffect {
	effects := map[int32]masterdata.EntityMQuestSceneChoiceEffect{}
	rows, _ := utils.ReadTable[masterdata.EntityMQuestSceneChoiceEffect]("m_quest_scene_choice_effect")
	for _, e := range rows {
		effects[e.QuestSceneChoiceEffectId] = e
	}
	out := map[sceneChoiceKey]masterdata.EntityMQuestSceneChoiceEffect{}
	choices, err := utils.ReadTable[masterdata.EntityMQuestSceneChoice]("m_quest_scene_choice")
	if err != nil {
		log.Printf("[QuestService] m_quest_scene_choice: %v", err)
	}
	for _, c := range choices {
		out[sceneChoiceKey{c.MainFlowQuestSceneId, c.QuestFlowType, c.ChoiceNumber}] = effects[c.QuestSceneChoiceEffectId]
	}
	return out
})

// recordSceneChoice saves a story choice; it returns false for a scene without choices.
func recordSceneChoice(u *store.UserState, sceneId, flowType, choice int32, now int64) bool {
	effect, ok := sceneChoices()[sceneChoiceKey{sceneId, flowType, choice}]
	if !ok {
		// Replays may report another flow type than the main story's.
		for k, e := range sceneChoices() {
			if k.sceneId == sceneId && k.choice == choice {
				effect, ok = e, true
				break
			}
		}
	}
	if !ok {
		return false
	}
	u.Ext.EnsureMaps()
	u.Ext.SceneChoices[effect.QuestSceneChoiceGroupingId] = store.SceneChoiceState{
		QuestSceneChoiceGroupingId: effect.QuestSceneChoiceGroupingId,
		QuestSceneChoiceEffectId:   effect.QuestSceneChoiceEffectId,
		LatestVersion:              now,
	}
	u.Ext.SceneChoiceHistory[effect.QuestSceneChoiceEffectId] = now
	return true
}

// IndividualPopServiceServer answers the game's question about unread pop-up notices: there are none offline.
type IndividualPopServiceServer struct {
	pb.UnimplementedIndividualPopServiceServer
}

func NewIndividualPopServiceServer() *IndividualPopServiceServer {
	return &IndividualPopServiceServer{}
}

func (s *IndividualPopServiceServer) GetUnreadPop(context.Context, *emptypb.Empty) (*pb.GetUnreadPopResponse, error) {
	return &pb.GetUnreadPopResponse{UnreadPop: []string{}}, nil
}

// GetDropItem lists items waiting in the Portal Cage; the master data names none.
func (s *PortalCageServiceServer) GetDropItem(context.Context, *emptypb.Empty) (*pb.GetDropItemResponse, error) {
	return &pb.GetDropItemResponse{PortalCageDropItem: []*pb.PortalCageDropItem{}}, nil
}

var cageDropPool = sync.OnceValue(func() []masterdata.EntityMCageOrnamentReward {
	rows, err := utils.ReadTable[masterdata.EntityMCageOrnamentReward]("m_cage_ornament_reward")
	if err != nil {
		log.Printf("[GimmickService] m_cage_ornament_reward: %v", err)
	}
	var pool []masterdata.EntityMCageOrnamentReward
	for _, r := range rows {
		if model.PossessionType(r.PossessionType) == model.PossessionTypeMaterial || model.PossessionType(r.PossessionType) == model.PossessionTypeConsumableItem {
			pool = append(pool, r)
		}
	}
	return pool
})

// cageDrop picks a reward for a Black Bird or Lost Item tap in the Cage. The
// master data has no table for these, so it draws from the Cage's ornament
// rewards (materials and items), each row equally likely.
func cageDrop() (model.PossessionType, int32, int32) {
	pool := cageDropPool()
	if len(pool) == 0 {
		return model.PossessionTypeMaterial, 100004, 1
	}
	r := pool[rand.Intn(len(pool))]
	return model.PossessionType(r.PossessionType), r.PossessionId, r.Count
}
