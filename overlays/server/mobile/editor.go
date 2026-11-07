package mobile

import (
	"encoding/json"
	"os"
	"path/filepath"

	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/lunarbase"
	"lunar-tear/server/internal/store"
)

// Edit executes Lunar Base against this app's save, only while gameplay is
// stopped (reads that change nothing excepted).
// Never accept a database path supplied by a web request.
func Edit(dataRoot, assetRoot, raw string) string {
	lifecycle.Lock()
	defer lifecycle.Unlock()
	fail := func(message string) string {
		b, _ := json.Marshal(map[string]any{"ok": false, "error": message})
		return string(b)
	}
	var request map[string]any
	if err := json.Unmarshal([]byte(raw), &request); err != nil {
		return fail(err.Error())
	}
	if target, ok := request["target"]; ok {
		if target != "deckbuilder_stage" {
			return fail("Unknown save target")
		}
		return editStage(dataRoot, assetRoot, request)
	}
	// Pod Programs › Gift's "how many can still be claimed" only reads the
	// save, so the game can play on; "send_gift" checks again with the
	// server stopped.
	if active != nil && request["action"] != "gift_room" {
		return fail("Stop the game server before editing saves")
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
	lunarbase.LiveGranter = liveGranter
	request["master_data_path"] = filepath.Join(assetRoot, "assets", "release", MasterName)
	encoded, err := json.Marshal(request)
	if err != nil {
		return fail(err.Error())
	}
	return lunarbase.Execute(encoded)
}

// editStage runs an edit on Pod Programs › Deck Builder's staging save
// (dataRoot/deckbuilder/stage.db), where fully raised pieces are built. It is
// never the player's save, so the game may keep playing; "stage_new" starts
// it over with an empty player 1. The caller holds lifecycle.
func editStage(dataRoot, assetRoot string, request map[string]any) string {
	path := filepath.Join(dataRoot, "deckbuilder", "stage.db")
	if request["action"] == "stage_new" {
		if err := lunarbase.NewStage(path); err != nil {
			b, _ := json.Marshal(map[string]any{"ok": false, "error": err.Error()})
			return string(b)
		}
		return `{"ok":true}`
	}
	if _, err := os.Stat(path); err != nil {
		return `{"ok":false,"error":"The Deck Builder stage is not ready"}`
	}
	request["db_path"] = path
	request["user_id"] = 1
	request["master_data_path"] = filepath.Join(assetRoot, "assets", "release", MasterName)
	encoded, err := json.Marshal(request)
	if err != nil {
		b, _ := json.Marshal(map[string]any{"ok": false, "error": err.Error()})
		return string(b)
	}
	return lunarbase.Execute(encoded)
}

// liveGranter is the running server's granter, or nil when it is stopped; the
// caller holds lifecycle.
func liveGranter() *store.PossessionGranter {
	if active == nil || active.granter == nil {
		return nil
	}
	return active.granter()
}
