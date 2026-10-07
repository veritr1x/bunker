package service

// The Arena against computer players (see internal/pvp): the PvP service, the
// defense deck, weekly reward claims and Arena info on profiles.

import (
	"context"
	"fmt"
	"log"
	"math/rand/v2"
	"time"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/pvp"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"

	emptypb "google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

type PvpServiceServer struct {
	pb.UnimplementedPvpServiceServer
	users    store.UserRepository
	sessions store.SessionRepository
	holder   *runtime.Holder
}

func NewPvpServiceServer(users store.UserRepository, sessions store.SessionRepository, holder *runtime.Holder) *PvpServiceServer {
	return &PvpServiceServer{users: users, sessions: sessions, holder: holder}
}

var errNoArena = fmt.Errorf("the Arena is not available")

// arena runs fn on the player's synced Arena state inside one save update.
func (s *PvpServiceServer) arena(ctx context.Context, fn func(c *pvp.Catalog, u *store.UserState, season masterdata.EntityMPvpSeason, ladder *pvp.Ladder, now int64)) error {
	c := pvp.Current()
	if c == nil {
		return errNoArena
	}
	now := gametime.NowMillis()
	userId := CurrentUserId(ctx, s.users, s.sessions)
	open := true
	_, err := s.users.UpdateUser(userId, func(u *store.UserState) {
		season, ladder, ok := c.Sync(u, now)
		if !ok {
			open = false
			return
		}
		fn(c, u, season, ladder, now)
	})
	if err != nil {
		return err
	}
	if !open {
		return errNoArena
	}
	return nil
}

func playerRand(u *store.UserState, now int64) *rand.Rand {
	return rand.New(rand.NewPCG(uint64(u.UserId), uint64(now)))
}

func (s *PvpServiceServer) GetTopData(ctx context.Context, _ *emptypb.Empty) (*pb.GetTopDataResponse, error) {
	resp := &pb.GetTopDataResponse{}
	err := s.arena(ctx, func(c *pvp.Catalog, u *store.UserState, season masterdata.EntityMPvpSeason, ladder *pvp.Ladder, now int64) {
		p := &u.Ext.Pvp
		resp.CurrentSeasonId, resp.PvpPoint, resp.Rank = season.PvpSeasonId, p.Point, ladder.Rank(p.Point)
	})
	log.Printf("[PvpService] GetTopData: season=%d point=%d rank=%d", resp.CurrentSeasonId, resp.PvpPoint, resp.Rank)
	return resp, err
}

func (s *PvpServiceServer) opponents(c *pvp.Catalog, u *store.UserState, ladder *pvp.Ladder) []*pb.MatchingOpponent {
	p := &u.Ext.Pvp
	profile := c.ProfileOf(u, store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: max(1, p.DefenseDeckNumber)})
	var out []*pb.MatchingOpponent
	for _, id := range p.Matching {
		cpu, ok := ladder.Get(id)
		if !ok {
			continue
		}
		out = append(out, &pb.MatchingOpponent{
			PlayerId:                    cpu.PlayerId,
			Name:                        cpu.Name,
			PvpPoint:                    cpu.Point,
			Rank:                        ladder.CPURank(cpu, p.Point),
			DeckPower:                   pvp.DeckPower(profile, pvp.Strength(cpu.Point, p.Point)),
			DeckMainWeaponAttributeType: c.MainWeaponAttributes(cpu),
			MostPowerfulCostumeId:       cpu.Costumes[0],
		})
	}
	return out
}

func (s *PvpServiceServer) GetMatchingList(ctx context.Context, _ *emptypb.Empty) (*pb.GetMatchingListResponse, error) {
	resp := &pb.GetMatchingListResponse{}
	err := s.arena(ctx, func(c *pvp.Catalog, u *store.UserState, season masterdata.EntityMPvpSeason, ladder *pvp.Ladder, now int64) {
		if len(u.Ext.Pvp.Matching) == 0 {
			c.Match(&u.Ext.Pvp, ladder, playerRand(u, now))
		}
		resp.Matching = s.opponents(c, u, ladder)
	})
	return resp, err
}

func (s *PvpServiceServer) UpdateMatchingList(ctx context.Context, _ *emptypb.Empty) (*pb.UpdateMatchingListResponse, error) {
	resp := &pb.UpdateMatchingListResponse{}
	err := s.arena(ctx, func(c *pvp.Catalog, u *store.UserState, season masterdata.EntityMPvpSeason, ladder *pvp.Ladder, now int64) {
		if c.Spend(&u.Ext.Pvp, c.RefreshCost, now) {
			c.Match(&u.Ext.Pvp, ladder, playerRand(u, now))
		} else {
			log.Printf("[PvpService] UpdateMatchingList: not enough battle points")
		}
		resp.Matching = s.opponents(c, u, ladder)
	})
	return resp, err
}

func (s *PvpServiceServer) StartBattle(ctx context.Context, req *pb.StartBattleRequest) (*pb.StartBattleResponse, error) {
	log.Printf("[PvpService] StartBattle: opponent=%d deck=%d", req.OpponentPlayerId, req.UseDeckNumber)
	resp := &pb.StartBattleResponse{}
	err := s.arena(ctx, func(c *pvp.Catalog, u *store.UserState, season masterdata.EntityMPvpSeason, ladder *pvp.Ladder, now int64) {
		cpu, ok := ladder.Get(req.OpponentPlayerId)
		if !ok {
			log.Printf("[PvpService] StartBattle: unknown opponent %d", req.OpponentPlayerId)
			return
		}
		if !c.Spend(&u.Ext.Pvp, c.BattleCost, now) {
			log.Printf("[PvpService] StartBattle: not enough battle points; battling anyway")
		}
		profile := c.ProfileOf(u, store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: req.UseDeckNumber})
		resp.OpponentDeckCharacter = c.Deck(cpu, profile, pvp.Strength(cpu.Point, u.Ext.Pvp.Point))
		u.Ext.Pvp.Opponent = cpu.PlayerId
	})
	return resp, err
}

func (s *PvpServiceServer) FinishBattle(ctx context.Context, req *pb.FinishBattleRequest) (*pb.FinishBattleResponse, error) {
	resp := &pb.FinishBattleResponse{}
	granter := s.holder.Get().QuestHandler.Granter
	err := s.arena(ctx, func(c *pvp.Catalog, u *store.UserState, season masterdata.EntityMPvpSeason, ladder *pvp.Ladder, now int64) {
		cpu, ok := ladder.Get(req.OpponentPlayerId)
		if !ok {
			log.Printf("[PvpService] FinishBattle: unknown opponent %d", req.OpponentPlayerId)
			return
		}
		r := playerRand(u, now)
		res := c.Finish(u, season, ladder, cpu, req.IsVictory, now, r)
		for _, rw := range res.Rewards {
			granter.GrantFull(u, rw.PossessionType, rw.PossessionId, rw.Count, now)
		}
		// A new set of opponents after each battle.
		c.Match(&u.Ext.Pvp, ladder, r)
		resp.BeforePvpPoint, resp.BeforeRank = res.BeforePoint, res.BeforeRank
		resp.AfterPvpPoint, resp.AfterRank = res.AfterPoint, res.AfterRank
		resp.PvpGradeOneMatchRewardId, resp.PvpGradeGroupId = res.OneMatchRewardId, res.GradeGroupId
	})
	log.Printf("[PvpService] FinishBattle: victory=%v points %d -> %d, rank %d -> %d", req.IsVictory, resp.BeforePvpPoint, resp.AfterPvpPoint, resp.BeforeRank, resp.AfterRank)
	return resp, err
}

const rankingPage = 50

func (s *PvpServiceServer) GetRanking(ctx context.Context, req *pb.GetRankingRequest) (*pb.GetRankingResponse, error) {
	resp := &pb.GetRankingResponse{}
	err := s.arena(ctx, func(c *pvp.Catalog, u *store.UserState, season masterdata.EntityMPvpSeason, ladder *pvp.Ladder, now int64) {
		p := &u.Ext.Pvp
		profile := c.ProfileOf(u, store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: max(1, p.DefenseDeckNumber)})
		for _, e := range ladder.Ranked(int(max(1, req.RankFrom)), rankingPage, p.Point) {
			if e.Player {
				resp.RankingUser = append(resp.RankingUser, &pb.RankingUser{
					Rank: e.Rank, PlayerId: u.UserId, Name: u.Profile.Name, PvpPoint: p.Point,
					DeckPower: pvp.DeckPower(profile, 1), FavoriteCostumeId: u.Profile.FavoriteCostumeId,
				})
				continue
			}
			resp.RankingUser = append(resp.RankingUser, &pb.RankingUser{
				Rank: e.Rank, PlayerId: e.CPU.PlayerId, Name: e.CPU.Name, PvpPoint: e.CPU.Point,
				DeckPower: pvp.DeckPower(profile, pvp.Strength(e.CPU.Point, p.Point)), FavoriteCostumeId: e.CPU.Costumes[0],
			})
		}
		resp.UserCount = int32(ladder.Size() + 1)
		resp.RankingPosition = ladder.Rank(p.Point)
	})
	return resp, err
}

func (s *PvpServiceServer) GetSeasonResult(ctx context.Context, _ *emptypb.Empty) (*pb.GetSeasonResultResponse, error) {
	resp := &pb.GetSeasonResultResponse{}
	err := s.arena(ctx, func(c *pvp.Catalog, u *store.UserState, season masterdata.EntityMPvpSeason, ladder *pvp.Ladder, now int64) {
		st := u.Ext.Pvp.Season
		resp.AttackWinCount, resp.AttackLoseCount, resp.AttackPvpPoint = st.AttackWins, st.AttackLosses, st.AttackPoint
		if n := st.DefenseWins + st.DefenseLosses; n > 0 {
			resp.DefenseWinRatePermil = st.DefenseWins * 1000 / n
		}
		resp.DefensePvpPoint = st.DefensePoint
	})
	return resp, err
}

func (s *PvpServiceServer) battleLogs(c *pvp.Catalog, u *store.UserState, ladder *pvp.Ladder, logs []store.PvpLog) []*pb.BattleLog {
	p := &u.Ext.Pvp
	profile := c.ProfileOf(u, store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: max(1, p.DefenseDeckNumber)})
	var out []*pb.BattleLog
	for _, l := range logs {
		cpu, ok := ladder.Get(l.PlayerId)
		if !ok {
			continue
		}
		var costumes []int32
		for _, id := range cpu.Costumes {
			if id != 0 {
				costumes = append(costumes, id)
			}
		}
		out = append(out, &pb.BattleLog{
			PlayerId: cpu.PlayerId, Name: cpu.Name, PvpPoint: l.Point,
			DeckPower: pvp.DeckPower(profile, pvp.Strength(l.Point, p.Point)), DeckCostumeId: costumes,
			IsVictory: l.Victory, BattleDatetime: timestamppb.New(time.UnixMilli(l.Datetime)),
			FluctuatedPvpPoint: l.Fluctuation, Rank: ladder.CPURank(cpu, p.Point),
		})
	}
	return out
}

func (s *PvpServiceServer) GetAttackLogList(ctx context.Context, _ *emptypb.Empty) (*pb.GetAttackLogListResponse, error) {
	resp := &pb.GetAttackLogListResponse{}
	err := s.arena(ctx, func(c *pvp.Catalog, u *store.UserState, season masterdata.EntityMPvpSeason, ladder *pvp.Ladder, now int64) {
		resp.AttackLog = s.battleLogs(c, u, ladder, u.Ext.Pvp.AttackLog)
	})
	return resp, err
}

func (s *PvpServiceServer) GetDefenseLogList(ctx context.Context, _ *emptypb.Empty) (*pb.GetDefenseLogListResponse, error) {
	resp := &pb.GetDefenseLogListResponse{}
	err := s.arena(ctx, func(c *pvp.Catalog, u *store.UserState, season masterdata.EntityMPvpSeason, ladder *pvp.Ladder, now int64) {
		resp.DefenseLog = s.battleLogs(c, u, ladder, u.Ext.Pvp.DefenseLog)
	})
	return resp, err
}

// SetPvpDefenseDeck chooses the deck computer players attack.
func (s *DeckServiceServer) SetPvpDefenseDeck(ctx context.Context, req *pb.SetPvpDefenseDeckRequest) (*pb.SetPvpDefenseDeckResponse, error) {
	log.Printf("[DeckService] SetPvpDefenseDeck: deck=%d power=%d", req.UserDeckNumber, req.GetDeckPower().GetPower())
	now := gametime.NowMillis()
	userId := CurrentUserId(ctx, s.users, s.sessions)
	if _, err := s.users.UpdateUser(userId, func(u *store.UserState) {
		p := &u.Ext.Pvp
		if p.DefenseDeckNumber == 0 {
			p.DefenseChecked = now // attacks start from now
		}
		p.DefenseDeckNumber = req.UserDeckNumber
		p.DefenseDeckPower = req.GetDeckPower().GetPower()
		p.LatestVersion = now
		key := store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: req.UserDeckNumber}
		if d, ok := u.Decks[key]; ok && req.GetDeckPower().GetPower() > 0 {
			d.Power = req.GetDeckPower().GetPower()
			u.Decks[key] = d
		}
	}); err != nil {
		return nil, err
	}
	return &pb.SetPvpDefenseDeckResponse{}, nil
}

// ReceivePvpReward pays the weekly grade and rank rewards of past weeks. The
// game calls it at the start when the weekly results show unpaid weeks.
func (s *RewardServiceServer) ReceivePvpReward(ctx context.Context, _ *emptypb.Empty) (*pb.ReceivePvpRewardResponse, error) {
	resp := &pb.ReceivePvpRewardResponse{}
	c := pvp.Current()
	if c == nil {
		return resp, nil
	}
	granter := s.holder.Get().QuestHandler.Granter
	now := gametime.NowMillis()
	userId := CurrentUserId(ctx, s.users, s.sessions)
	paid := 0
	if _, err := s.users.UpdateUser(userId, func(u *store.UserState) {
		if _, _, ok := c.Sync(u, now); !ok {
			return
		}
		pending := c.PendingWeekly(&u.Ext.Pvp)
		for _, w := range pending {
			for _, r := range w.Rewards {
				granter.GrantFull(u, r.PossessionType, r.PossessionId, r.Count, now)
				paid++
			}
		}
		if len(pending) == 0 {
			return
		}
		last := pending[len(pending)-1]
		resp.WeeklyGradeResult = &pb.WeeklyGradeResult{
			TargetSeasonId: last.Result.SeasonId, PvpPoint: last.Result.FinalPoint, PvpGradeWeeklyRewardGroupId: last.GradeRewardGroup,
		}
		resp.WeeklyRankResult = &pb.WeeklyRankResult{
			TargetSeasonId: last.Result.SeasonId, Rank: last.Result.FinalRank, PvpWeeklyRankRewardGroupId: last.RankGroup,
		}
		u.Ext.Pvp.RewardWeekVersion = last.Result.WeekVersion
		u.Ext.Pvp.LatestVersion = now
	}); err != nil {
		return nil, err
	}
	log.Printf("[RewardService] ReceivePvpReward: paid %d item(s)", paid)
	return resp, nil
}

// pvpProfileInfo is the Arena part of the player's profile.
func pvpProfileInfo(u store.UserState) *pb.ProfilePvpInfo {
	info := &pb.ProfilePvpInfo{}
	c := pvp.Current()
	if c == nil {
		return info
	}
	season, ok := c.Season(gametime.NowMillis())
	if !ok || u.Ext.Pvp.SeasonId != season.PvpSeasonId {
		return info
	}
	info.CurrentRank = c.Ladder(season.PvpSeasonId).Rank(u.Ext.Pvp.Point)
	info.CurrentGradeId = c.Grade(season, u.Ext.Pvp.Point).PvpGradeId
	info.MaxSeasonRank = u.Ext.Pvp.MaxSeasonRank
	return info
}

// cpuProfile is a computer player's profile, or nil for other ids.
func (s *UserServiceServer) cpuProfile(ctx context.Context, playerId int64) *pb.GetUserProfileResponse {
	c := pvp.Current()
	if c == nil || !pvp.IsCPU(playerId) {
		return nil
	}
	now := gametime.NowMillis()
	season, ok := c.Season(now)
	if !ok {
		return nil
	}
	ladder := c.Ladder(season.PvpSeasonId)
	cpu, ok := ladder.Get(playerId)
	if !ok {
		return nil
	}
	viewer, err := s.users.LoadUser(CurrentUserId(ctx, s.users, s.sessions))
	if err != nil {
		return nil
	}
	strength := pvp.Strength(cpu.Point, viewer.Ext.Pvp.Point)
	profile := c.ProfileOf(&viewer, store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: max(1, viewer.Ext.Pvp.DefenseDeckNumber)})
	deck := c.Deck(cpu, profile, strength)
	var chars []*pb.ProfileDeckCharacter
	for _, d := range deck {
		chars = append(chars, &pb.ProfileDeckCharacter{
			CostumeId: d.GetCostume().GetCostumeId(), MainWeaponId: d.GetMainWeapon().GetWeaponId(), MainWeaponLevel: d.GetMainWeapon().GetLevel(),
		})
	}
	level := int32(1)
	if len(deck) > 0 {
		level = max(1, min(150, deck[0].GetCostume().GetCharacterLevel()))
	}
	return &pb.GetUserProfileResponse{
		Level:             level,
		Name:              cpu.Name,
		FavoriteCostumeId: cpu.Costumes[0],
		LatestUsedDeck:    &pb.ProfileDeck{Power: pvp.DeckPower(profile, strength), DeckCharacter: chars},
		PvpInfo: &pb.ProfilePvpInfo{
			CurrentRank: ladder.CPURank(cpu, viewer.Ext.Pvp.Point), CurrentGradeId: c.Grade(season, cpu.Point).PvpGradeId,
			MaxSeasonRank: ladder.CPURank(cpu, viewer.Ext.Pvp.Point),
		},
		GamePlayHistory: &pb.GamePlayHistory{HistoryItem: []*pb.PlayHistoryItem{}, HistoryCategoryGraphItem: []*pb.PlayHistoryCategoryGraphItem{}},
	}
}
