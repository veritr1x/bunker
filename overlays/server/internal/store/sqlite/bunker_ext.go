package sqlite

import (
	"database/sql"
	"encoding/json"
	"log"

	"lunar-tear/server/internal/store"
)

// loadExt reads Bunker's JSON save document; a missing or unreadable one is empty.
func loadExt(db *sql.DB, uid int64, u *store.UserState) {
	var data string
	err := db.QueryRow(`SELECT data FROM user_bunker_ext WHERE user_id = ?`, uid).Scan(&data)
	if err == nil {
		if err = json.Unmarshal([]byte(data), &u.Ext); err != nil {
			log.Printf("[sqlite] user %d: unreadable user_bunker_ext: %v", uid, err)
		}
	} else if err != sql.ErrNoRows {
		log.Printf("[sqlite] user %d: load user_bunker_ext: %v", uid, err)
	}
	u.Ext.EnsureMaps()
}

func saveExt(tx *sql.Tx, uid int64, ext store.ExtState) error {
	data, err := json.Marshal(ext)
	if err != nil {
		return err
	}
	_, err = tx.Exec(`INSERT INTO user_bunker_ext (user_id, data) VALUES (?, ?)
		ON CONFLICT(user_id) DO UPDATE SET data = excluded.data`, uid, string(data))
	return err
}
