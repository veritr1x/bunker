package mobile

import (
	"encoding/json"
	"os"
	"path/filepath"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/lunarbase"
)

// Edit executes Lunar Base against this app's save, only while gameplay is stopped.
// Never accept a database path supplied by a web request.
func Edit(dataRoot, assetRoot, raw string) string {
	lifecycle.Lock()
	defer lifecycle.Unlock()
	fail := func(message string) string {
		b, _ := json.Marshal(map[string]any{"ok": false, "error": message})
		return string(b)
	}
	if active != nil {
		return fail("Stop the game server before editing saves")
	}
	var request map[string]any
	if err := json.Unmarshal([]byte(raw), &request); err != nil {
		return fail(err.Error())
	}
	path := filepath.Join(dataRoot, "game.db")
	if _, err := os.Stat(path); err != nil {
		return fail("Play the game once before using save editors")
	}
	db, err := database.Open(path)
	if err != nil {
		return fail(err.Error())
	}
	var count int
	err = db.QueryRow("SELECT COUNT(*) FROM users WHERE user_id = ?", request["user_id"]).Scan(&count)
	db.Close()
	if err != nil {
		return fail(err.Error())
	}
	if count != 1 {
		return fail("Player not found")
	}
	request["db_path"] = path
	request["master_data_path"] = filepath.Join(assetRoot, "assets", "release", MasterName)
	encoded, err := json.Marshal(request)
	if err != nil {
		return fail(err.Error())
	}
	return lunarbase.Execute(encoded)
}
