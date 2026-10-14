package service

import (
	"testing"
	"time"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
)

// memUsers is one player kept in memory, for driving handlers in tests.
type memUsers struct{ user store.UserState }

func newMemUsers() *memUsers {
	return &memUsers{user: *store.SeedUserState(1, "test", 1_700_000_000_000, model.DefaultPlatform)}
}

func (m *memUsers) CreateUser(string, model.ClientPlatform) (int64, error) { return 1, nil }
func (m *memUsers) GetUserByUUID(string) (int64, error)                    { return 1, nil }
func (m *memUsers) LoadUser(int64) (store.UserState, error)                { return store.CloneUserState(m.user), nil }
func (m *memUsers) UpdateUser(_ int64, mutate func(*store.UserState)) (store.UserState, error) {
	mutate(&m.user)
	return store.CloneUserState(m.user), nil
}
func (m *memUsers) DefaultUserId() (int64, error)            { return 1, nil }
func (m *memUsers) SetFacebookId(int64, int64) error         { return nil }
func (m *memUsers) GetUserByFacebookId(int64) (int64, error) { return 0, nil }
func (m *memUsers) GetFacebookId(int64) (int64, error)       { return 0, nil }
func (m *memUsers) ClearFacebookId(int64) error              { return nil }
func (m *memUsers) UpdateUUID(int64, string) error           { return nil }
func (m *memUsers) CreateSession(string, time.Duration) (store.SessionState, error) {
	return store.SessionState{}, nil
}
func (m *memUsers) ResolveUserId(string) (int64, error) { return 1, nil }

// harness is the original master data and one player.
func harness(t *testing.T) (*runtime.Holder, *memUsers) {
	t.Helper()
	return loadMaster(t), newMemUsers()
}

// setClock moves the game clock to at (through the calendar's shift, which
// leaves the game data's dates where they are) until the test ends.
func setClock(t *testing.T, at int64) {
	t.Helper()
	gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: gametime.Launch, Speed: 1, JumpMillis: at - time.Now().UnixMilli()})
	t.Cleanup(func() { gametime.SetCalendar(nil) })
}
