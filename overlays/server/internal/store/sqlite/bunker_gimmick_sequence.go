package sqlite

import "fmt"

// EnsureGimmickSequence adds a not-cleared gimmick sequence row unless the
// save has it, in one statement instead of a whole UpdateUser (the game sends
// UpdateSequence for each sequence while a map loads). An existing row, which
// may be cleared, is left alone. ok is false when the save already holds
// maxRows sequences and lacks this one: the caller then takes the full update.
// From the JCalandre/lunar-tear fork, with the row cap added.
func (s *SQLiteStore) EnsureGimmickSequence(userId int64, scheduleId, sequenceId int32, maxRows int) (added, ok bool, err error) {
	unlock := s.lockUser(userId)
	defer unlock()
	res, err := s.db.Exec(`INSERT OR IGNORE INTO user_gimmick_sequences
		(user_id, gimmick_sequence_schedule_id, gimmick_sequence_id, is_gimmick_sequence_cleared, clear_datetime, latest_version)
		SELECT ?, ?, ?, 0, 0, 0
		WHERE (SELECT COUNT(*) FROM user_gimmick_sequences WHERE user_id = ?) < ?`,
		userId, scheduleId, sequenceId, userId, maxRows)
	if err != nil {
		return false, false, fmt.Errorf("ensure gimmick sequence: %w", err)
	}
	if n, _ := res.RowsAffected(); n > 0 {
		return true, true, nil
	}
	var exists int
	err = s.db.QueryRow(`SELECT COUNT(*) FROM user_gimmick_sequences
		WHERE user_id = ? AND gimmick_sequence_schedule_id = ? AND gimmick_sequence_id = ?`,
		userId, scheduleId, sequenceId).Scan(&exists)
	if err != nil {
		return false, false, fmt.Errorf("ensure gimmick sequence: %w", err)
	}
	return false, exists > 0, nil
}
