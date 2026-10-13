package store

import (
	"reflect"
	"slices"
)

// FriendState is the player's friends: offline there are no other players,
// so they are the Arena's computer players (see service/bunker_friends.go).
// Cheers are counted per game day (Day is its start).
type FriendState struct {
	Friends   []int64 `json:"friends,omitempty"`  // player ids, in the order they became friends
	Day       int64   `json:"day,omitempty"`      // the day Sent and Received are for
	Sent      []int64 `json:"sent,omitempty"`     // friends cheered on Day
	Received  []int64 `json:"received,omitempty"` // friends whose cheer was taken on Day
	TotalSent int64   `json:"totalSent,omitempty"`
}

func (f FriendState) Clone() FriendState {
	out := f
	out.Friends = slices.Clone(f.Friends)
	out.Sent = slices.Clone(f.Sent)
	out.Received = slices.Clone(f.Received)
	return out
}

func (f FriendState) Equal(o FriendState) bool { return reflect.DeepEqual(f, o) }

// LastDeckState is the deck the player last fought with (from the client's
// FinishWave), shown on their profile card.
type LastDeckState struct {
	DeckType       int32 `json:"deckType,omitempty"`
	UserDeckNumber int32 `json:"userDeckNumber,omitempty"`
}
