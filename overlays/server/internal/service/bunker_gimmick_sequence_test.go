package service

import (
	"context"
	"strings"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/store"
)

// sequenceUsers is memUsers with the one-row fast path, counting full loads.
type sequenceUsers struct {
	*memUsers
	loads, updates int
	full           bool // the save is at the row cap
}

func (s *sequenceUsers) LoadUser(id int64) (store.UserState, error) {
	s.loads++
	return s.memUsers.LoadUser(id)
}

func (s *sequenceUsers) UpdateUser(id int64, mutate func(*store.UserState)) (store.UserState, error) {
	s.updates++
	return s.memUsers.UpdateUser(id, mutate)
}

func (s *sequenceUsers) EnsureGimmickSequence(_ int64, scheduleId, sequenceId int32, maxRows int) (bool, bool, error) {
	if s.full {
		return false, false, nil
	}
	key := store.GimmickSequenceKey{GimmickSequenceScheduleId: scheduleId, GimmickSequenceId: sequenceId}
	if _, ok := s.user.Gimmick.Sequences[key]; ok {
		return false, true, nil
	}
	s.user.Gimmick.Sequences[key] = store.GimmickSequenceState{Key: key}
	return true, true, nil
}

// UpdateSequence (sent for each sequence while a map loads) adds its row
// without loading the save, and sends the game the new row itself.
func TestUpdateSequenceWritesOneRow(t *testing.T) {
	ctx := context.Background()
	req := &pb.UpdateSequenceRequest{GimmickSequenceScheduleId: 7, GimmickSequenceId: 70}
	check := func(name string, resp *pb.UpdateSequenceResponse, wantRow bool) {
		t.Helper()
		d := resp.DiffUserData["IUserGimmickSequence"]
		if got := d != nil && strings.Contains(d.UpdateRecordsJson, `"gimmickSequenceId":70`); got != wantRow {
			t.Fatalf("%s: diff %v, want the row %v", name, resp.DiffUserData, wantRow)
		}
		if wantRow && len(resp.DiffUserData) != 1 {
			t.Fatalf("%s: diff has other tables: %v", name, resp.DiffUserData)
		}
	}

	fast := &sequenceUsers{memUsers: newMemUsers()}
	srv := NewGimmickServiceServer(fast, fast, nil)
	resp, err := srv.UpdateSequence(ctx, req)
	if err != nil {
		t.Fatal(err)
	}
	check("new row", resp, true)
	resp, _ = srv.UpdateSequence(ctx, req)
	check("existing row", resp, false)
	if fast.loads != 0 || fast.updates != 0 {
		t.Fatalf("fast path loaded the save %d times, updated %d", fast.loads, fast.updates)
	}

	// At the row cap, or without the fast path, the full update runs.
	full := &sequenceUsers{memUsers: newMemUsers(), full: true}
	resp, err = NewGimmickServiceServer(full, full, nil).UpdateSequence(ctx, req)
	if err != nil {
		t.Fatal(err)
	}
	check("full save", resp, true)
	if full.updates != 1 {
		t.Fatalf("full save: %d updates", full.updates)
	}
	plain := newMemUsers()
	resp, _ = NewGimmickServiceServer(plain, plain, nil).UpdateSequence(ctx, req)
	check("plain store", resp, true)
	resp, _ = NewGimmickServiceServer(plain, plain, nil).UpdateSequence(ctx, req)
	check("plain store again", resp, false)
}
