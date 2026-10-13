package service

// Friends offline: there are no other players, so the Arena's computer players
// stand in for friends (see internal/pvp/friends.go). They show up as
// recommended players, accept a friend request at once and send the player
// support every day; cheering them counts for the "Send a friend support"
// missions, which otherwise kept the daily missions from completing.

import (
	"context"
	"log"
	"time"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/pvp"
	"lunar-tear/server/internal/store"

	emptypb "google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// cpuCard is how a computer player shows in friend lists: level, deck power
// and favorite costume, as on its profile (cpuProfile).
type cpuCard struct {
	cpu       pvp.CPU
	level     int32
	power     int32
	lastLogin time.Time
}

// friendWorld is the Arena's ladder this season, with the player's own deck
// to scale the computer players against.
type friendWorld struct {
	c      *pvp.Catalog
	ladder *pvp.Ladder
	user   *store.UserState
}

func newFriendWorld(u *store.UserState) (friendWorld, bool) {
	c := pvp.Current()
	if c == nil {
		return friendWorld{}, false
	}
	season, ok := c.Season(gametime.NowMillis())
	if !ok {
		return friendWorld{}, false
	}
	return friendWorld{c: c, ladder: c.Ladder(season.PvpSeasonId), user: u}, true
}

func (w friendWorld) card(playerId int64, now int64) (cpuCard, bool) {
	cpu, ok := w.ladder.Get(playerId)
	if !ok {
		return cpuCard{}, false
	}
	strength := pvp.Strength(cpu.Point, w.user.Ext.Pvp.Point)
	profile := w.c.ProfileOf(w.user, store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: max(1, w.user.Ext.Pvp.DefenseDeckNumber)})
	card := cpuCard{cpu: cpu, level: 1, power: pvp.DeckPower(profile, strength)}
	if deck := w.c.Deck(cpu, profile, strength); len(deck) > 0 {
		card.level = max(1, min(150, deck[0].GetCostume().GetCharacterLevel()))
	}
	// Seen within the last few hours, a different time for each.
	card.lastLogin = time.UnixMilli(now - (playerId%240)*60*1000)
	return card, true
}

func (c cpuCard) user() *pb.User {
	return &pb.User{PlayerId: c.cpu.PlayerId, UserName: c.cpu.Name, LastLoginDatetime: timestamppb.New(c.lastLogin),
		MaxDeckPower: c.power, FavoriteCostumeId: c.cpu.Costumes[0], Level: c.level}
}

// cheerDay is the game day cheers are counted for.
func cheerDay() int64 { return gametime.StartOfDayMillis() }

func (s *FriendServiceServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
	log.Printf("[FriendService] GetUser: playerId=%d", req.PlayerId)
	u, err := s.users.LoadUser(CurrentUserId(ctx, s.users, s.sessions))
	if err != nil {
		return &pb.GetUserResponse{}, nil
	}
	w, ok := newFriendWorld(&u)
	if !ok {
		return &pb.GetUserResponse{}, nil
	}
	card, ok := w.card(req.PlayerId, gametime.NowMillis())
	if !ok {
		return &pb.GetUserResponse{}, nil
	}
	return &pb.GetUserResponse{User: card.user()}, nil
}

func (s *FriendServiceServer) GetFriendList(ctx context.Context, req *pb.GetFriendListRequest) (*pb.GetFriendListResponse, error) {
	resp := &pb.GetFriendListResponse{FriendUser: []*pb.FriendUser{}}
	u, err := s.users.LoadUser(CurrentUserId(ctx, s.users, s.sessions))
	if err != nil {
		return resp, nil
	}
	w, ok := newFriendWorld(&u)
	if !ok {
		return resp, nil
	}
	now, day := gametime.NowMillis(), cheerDay()
	f := &u.Ext.Friends
	for _, id := range f.Friends {
		card, ok := w.card(id, now)
		if !ok {
			continue
		}
		sent, received := pvp.CheerStatus(f, id, day)
		resp.FriendUser = append(resp.FriendUser, &pb.FriendUser{
			PlayerId: id, UserName: card.cpu.Name, LastLoginDatetime: timestamppb.New(card.lastLogin),
			MaxDeckPower: card.power, FavoriteCostumeId: card.cpu.Costumes[0], Level: card.level,
			CheerReceived: true, CheerSent: sent, StaminaReceived: received,
		})
	}
	resp.SendCheerCount, resp.ReceivedCheerCount = int32(pvp.SentToday(f, day)), int32(pvp.ReceivedToday(f, day))
	log.Printf("[FriendService] GetFriendList: %d friends, %d cheers sent, %d received today", len(resp.FriendUser), resp.SendCheerCount, resp.ReceivedCheerCount)
	return resp, nil
}

func (s *FriendServiceServer) SearchRecommendedUsers(ctx context.Context, _ *emptypb.Empty) (*pb.SearchRecommendedUsersResponse, error) {
	resp := &pb.SearchRecommendedUsersResponse{Users: []*pb.User{}}
	u, err := s.users.LoadUser(CurrentUserId(ctx, s.users, s.sessions))
	if err != nil {
		return resp, nil
	}
	w, ok := newFriendWorld(&u)
	if !ok {
		return resp, nil
	}
	now := gametime.NowMillis()
	for _, cpu := range w.c.Recommend(&u.Ext.Friends, w.ladder, u.Ext.Pvp.Point, u.UserId, cheerDay()) {
		if card, ok := w.card(cpu.PlayerId, now); ok {
			resp.Users = append(resp.Users, card.user())
		}
	}
	return resp, nil
}

// updateFriends changes the player's friends; fn reports whether it did anything.
func (s *FriendServiceServer) updateFriends(ctx context.Context, fn func(c *pvp.Catalog, u *store.UserState, now int64) bool) bool {
	c := pvp.Current()
	if c == nil {
		return false
	}
	changed := false
	s.users.UpdateUser(CurrentUserId(ctx, s.users, s.sessions), func(u *store.UserState) {
		changed = fn(c, u, gametime.NowMillis())
	})
	return changed
}

// cheerStamina gives the stamina for one cheer sent or received.
func cheerStamina(u *store.UserState, now int64) {
	var maxMillis int32
	if bunkerHolder != nil {
		if cats := bunkerHolder.Get(); cats != nil && cats.Shop != nil {
			maxMillis = cats.Shop.MaxStaminaMillis[u.Status.Level]
		}
	}
	store.RecoverStamina(u, pvp.CheerStaminaMillis, maxMillis, now)
}

func (s *FriendServiceServer) SendFriendRequest(ctx context.Context, req *pb.SendFriendRequestRequest) (*pb.SendFriendRequestResponse, error) {
	// Computer players accept at once.
	added := s.updateFriends(ctx, func(c *pvp.Catalog, u *store.UserState, _ int64) bool {
		return c.AddFriend(&u.Ext.Friends, req.PlayerId)
	})
	log.Printf("[FriendService] SendFriendRequest: playerId=%d accepted=%v", req.PlayerId, added)
	return &pb.SendFriendRequestResponse{}, nil
}

func (s *FriendServiceServer) AcceptFriendRequest(context.Context, *pb.AcceptFriendRequestRequest) (*pb.AcceptFriendRequestResponse, error) {
	return &pb.AcceptFriendRequestResponse{}, nil
}

func (s *FriendServiceServer) DeclineFriendRequest(context.Context, *pb.DeclineFriendRequestRequest) (*pb.DeclineFriendRequestResponse, error) {
	return &pb.DeclineFriendRequestResponse{}, nil
}

func (s *FriendServiceServer) DeleteFriend(ctx context.Context, req *pb.DeleteFriendRequest) (*pb.DeleteFriendResponse, error) {
	s.updateFriends(ctx, func(_ *pvp.Catalog, u *store.UserState, _ int64) bool {
		pvp.RemoveFriend(&u.Ext.Friends, req.PlayerId)
		return true
	})
	return &pb.DeleteFriendResponse{}, nil
}

func (s *FriendServiceServer) CheerFriend(ctx context.Context, req *pb.CheerFriendRequest) (*pb.CheerFriendResponse, error) {
	sent := s.updateFriends(ctx, func(c *pvp.Catalog, u *store.UserState, now int64) bool {
		if !c.Cheer(&u.Ext.Friends, req.PlayerId, cheerDay()) {
			return false
		}
		cheerStamina(u, now)
		return true
	})
	log.Printf("[FriendService] CheerFriend: playerId=%d sent=%v", req.PlayerId, sent)
	return &pb.CheerFriendResponse{}, nil
}

func (s *FriendServiceServer) BulkCheerFriend(ctx context.Context, _ *emptypb.Empty) (*pb.BulkCheerFriendResponse, error) {
	resp := &pb.BulkCheerFriendResponse{PlayerId: []int64{}}
	s.updateFriends(ctx, func(c *pvp.Catalog, u *store.UserState, now int64) bool {
		for _, id := range u.Ext.Friends.Friends {
			if c.Cheer(&u.Ext.Friends, id, cheerDay()) {
				cheerStamina(u, now)
				resp.PlayerId = append(resp.PlayerId, id)
			}
		}
		return len(resp.PlayerId) > 0
	})
	log.Printf("[FriendService] BulkCheerFriend: %d sent", len(resp.PlayerId))
	return resp, nil
}

func (s *FriendServiceServer) ReceiveCheer(ctx context.Context, req *pb.ReceiveCheerRequest) (*pb.ReceiveCheerResponse, error) {
	s.updateFriends(ctx, func(c *pvp.Catalog, u *store.UserState, now int64) bool {
		if !c.ReceiveCheer(&u.Ext.Friends, req.PlayerId, cheerDay()) {
			return false
		}
		cheerStamina(u, now)
		return true
	})
	return &pb.ReceiveCheerResponse{}, nil
}

func (s *FriendServiceServer) BulkReceiveCheer(ctx context.Context, _ *emptypb.Empty) (*pb.BulkReceiveCheerResponse, error) {
	resp := &pb.BulkReceiveCheerResponse{PlayerId: []int64{}}
	s.updateFriends(ctx, func(c *pvp.Catalog, u *store.UserState, now int64) bool {
		for _, id := range u.Ext.Friends.Friends {
			if c.ReceiveCheer(&u.Ext.Friends, id, cheerDay()) {
				cheerStamina(u, now)
				resp.PlayerId = append(resp.PlayerId, id)
			}
		}
		return len(resp.PlayerId) > 0
	})
	log.Printf("[FriendService] BulkReceiveCheer: %d received", len(resp.PlayerId))
	return resp, nil
}
