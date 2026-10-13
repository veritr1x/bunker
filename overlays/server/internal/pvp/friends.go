package pvp

import (
	"math"
	"math/rand/v2"
	"slices"

	"lunar-tear/server/internal/store"
)

// Friends offline: the player is alone, so the Arena's computer players stand
// in for friends. They accept a friend request at once and send the player
// support (a cheer) every day, as an active friend would. The limits are the
// game's (m_config USER_FRIEND_*); a request over a limit changes nothing.

// CheerStaminaMillis is the stamina sending or receiving one cheer gives
// ("{0} stamina gained for sending support to a friend."). The amount is not
// in the master data or the client; this is a guess.
const CheerStaminaMillis = 1000

// recommendCount is how many players SearchRecommendedUsers offers.
const recommendCount = 10

// FriendLimits are the m_config friend limits.
type FriendLimits struct {
	Friends, SendCheer, ReceiveCheer int
}

// newDay starts the day's cheer counts over.
func newDay(f *store.FriendState, day int64) {
	if f.Day != day {
		f.Day, f.Sent, f.Received = day, nil, nil
	}
}

// IsFriend reports whether a player is the player's friend.
func IsFriend(f *store.FriendState, playerId int64) bool { return slices.Contains(f.Friends, playerId) }

// AddFriend makes a computer player a friend; false if it is not one, is
// already a friend or the friend list is full.
func (c *Catalog) AddFriend(f *store.FriendState, playerId int64) bool {
	if !IsCPU(playerId) || IsFriend(f, playerId) || len(f.Friends) >= c.Friend.Friends {
		return false
	}
	f.Friends = append(f.Friends, playerId)
	return true
}

// RemoveFriend drops a friend. Today's cheers stay counted, so removing and
// re-adding a friend doesn't allow another cheer.
func RemoveFriend(f *store.FriendState, playerId int64) {
	f.Friends = slices.DeleteFunc(f.Friends, func(id int64) bool { return id == playerId })
}

// CheerStatus is what the friend list shows for one friend today.
func CheerStatus(f *store.FriendState, playerId int64, day int64) (sent, received bool) {
	if f.Day != day {
		return false, false
	}
	return slices.Contains(f.Sent, playerId), slices.Contains(f.Received, playerId)
}

// SentToday and ReceivedToday are the day's cheer counts.
func SentToday(f *store.FriendState, day int64) int {
	if f.Day != day {
		return 0
	}
	return len(f.Sent)
}

func ReceivedToday(f *store.FriendState, day int64) int {
	if f.Day != day {
		return 0
	}
	return len(f.Received)
}

// Cheer sends support to a friend: once per friend per day, at most
// USER_FRIEND_SEND_CHEER_MAX_NUMBER a day.
func (c *Catalog) Cheer(f *store.FriendState, playerId, day int64) bool {
	newDay(f, day)
	if !IsFriend(f, playerId) || slices.Contains(f.Sent, playerId) || len(f.Sent) >= c.Friend.SendCheer {
		return false
	}
	f.Sent = append(f.Sent, playerId)
	f.TotalSent++
	return true
}

// ReceiveCheer takes a friend's support: every computer friend sends one a
// day; at most USER_FRIEND_RECEIVE_CHEER_MAX_NUMBER are taken a day.
func (c *Catalog) ReceiveCheer(f *store.FriendState, playerId, day int64) bool {
	newDay(f, day)
	if !IsFriend(f, playerId) || slices.Contains(f.Received, playerId) || len(f.Received) >= c.Friend.ReceiveCheer {
		return false
	}
	f.Received = append(f.Received, playerId)
	return true
}

// Recommend offers computer players near the player's Arena points who are
// not friends yet; the same ones all day.
func (c *Catalog) Recommend(f *store.FriendState, ladder *Ladder, point int32, userId, day int64) []CPU {
	r := rand.New(rand.NewPCG(uint64(userId), uint64(day)))
	skip := map[int64]bool{}
	for _, id := range f.Friends {
		skip[id] = true
	}
	var out []CPU
	for len(out) < recommendCount && len(skip) < ladder.Size() {
		cpu, ok := ladder.Near(max(0, point+r.Int32N(3000)-1500), skip, r)
		if !ok {
			break
		}
		skip[cpu.PlayerId] = true
		out = append(out, cpu)
	}
	return out
}

// Computer players' accounts, for their friend cards and profiles. The ranges
// are a guess at players of each Arena band (the original players' are not
// known): from a new account at 0 points to a long-played one at the top.
const (
	cardLevelLow, cardLevelHigh = 15, 250
	cardPowerLow, cardPowerHigh = 10000, 180000
)

// Card is a computer player's user level and deck power as its friend card and
// profile show them: its own, the same each time (seeded by its id), higher
// the more Arena points it has. Battles don't use it: Deck builds the
// opponent against the player's own deck.
func (c *Catalog) Card(cpu CPU) (level, power int32) {
	r := rand.New(rand.NewPCG(uint64(cpu.PlayerId), 0x5ca1ab1e))
	band := math.Max(0, math.Min(1, float64(cpu.Point)/topPoint))
	jitter := func(spread float64) float64 { return 1 + spread*(2*r.Float64()-1) }
	level = int32(math.Round((cardLevelLow + (cardLevelHigh-cardLevelLow)*math.Pow(band, 0.6)) * jitter(0.15)))
	power = int32(math.Round((cardPowerLow + (cardPowerHigh-cardPowerLow)*math.Pow(band, 0.8)) * jitter(0.12)))
	return max(1, min(level, c.maxUserLevel())), power
}

// maxUserLevel is the highest user level in the master data.
func (c *Catalog) maxUserLevel() int32 {
	if c.cats != nil && c.cats.Quest != nil && len(c.cats.Quest.UserExpThresholds) > 1 {
		return int32(len(c.cats.Quest.UserExpThresholds) - 1)
	}
	return cardLevelHigh
}
