package mobile

import (
	"encoding/json"
	"fmt"
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
	// Deck Builder's matching list ("arena_matching") only reads the save too.
	if active != nil && request["action"] != "gift_room" && request["action"] != "arena_matching" {
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
	request = editRequest(dataRoot, request)
	lunarbase.LiveGranter = liveGranter
	request["master_data_path"] = filepath.Join(assetRoot, "assets", "release", MasterName)
	encoded, err := json.Marshal(request)
	if err != nil {
		return fail(err.Error())
	}
	return lunarbase.Execute(encoded)
}

// editRequest fixes the paths an edit of the player's save uses: the app's
// own save, and Deck Builder's stage for a deck write. Paths in the request
// are never used.
func editRequest(dataRoot string, request map[string]any) map[string]any {
	request["db_path"] = filepath.Join(dataRoot, "game.db")
	request["stage_path"] = filepath.Join(dataRoot, "deckbuilder", "stage.db")
	return request
}

// editStage runs an edit on Pod Programs › Deck Builder's staging save
// (dataRoot/deckbuilder/stage.db), where fully raised pieces are built. It is
// never the player's save, so the game may keep playing; "stage_new" starts
// it over with an empty player 1. The caller holds lifecycle.
func editStage(dataRoot, assetRoot string, request map[string]any) string {
	fail := func(message string) string {
		b, _ := json.Marshal(map[string]any{"ok": false, "error": message})
		return string(b)
	}
	action, _ := request["action"].(string)
	if !stageActions[action] {
		return fail(fmt.Sprintf("%q is not a stage action", action))
	}
	// The stage's actions load the master data, which the running server reads
	// too: they wait for it to be stopped (the game guard pauses it).
	if active != nil {
		return fail("Stop the game server before building the Deck Builder stage")
	}
	path := filepath.Join(dataRoot, "deckbuilder", "stage.db")
	if action == "stage_new" {
		if err := lunarbase.NewStage(path); err != nil {
			return fail(err.Error())
		}
		return `{"ok":true}`
	}
	if _, err := os.Stat(path); err != nil {
		return fail("The Deck Builder stage is not ready")
	}
	encoded, err := json.Marshal(stageRequest(dataRoot, filepath.Join(assetRoot, "assets", "release", MasterName), request))
	if err != nil {
		return fail(err.Error())
	}
	return lunarbase.Execute(encoded)
}

// stageActions are the actions the stage is built with (deckbuilder/stage.py).
var stageActions = map[string]bool{
	"stage_new": true, "grant_costume_batch": true, "grant_weapon_batch": true, "grant_companion_batch": true,
	"grant_thought_batch": true, "exalt_characters": true, "upgrade_all_costumes": true, "upgrade_all_weapons": true,
	"upgrade_all_companions": true, "release_panels": true, "fill_karma_slots": true, "grant_memoir_batch": true,
	"upgrade_all_memoirs": true, "set_costume_karma_batch": true, "rank_characters": true, "grant_batch": true,
}

// stageRequest points an edit at the stage, whatever paths the request named.
func stageRequest(dataRoot, master string, request map[string]any) map[string]any {
	delete(request, "stage_path")
	delete(request, "target")
	request["db_path"] = filepath.Join(dataRoot, "deckbuilder", "stage.db")
	request["user_id"] = 1
	request["master_data_path"] = master
	return request
}

// liveGranter is the running server's granter, or nil when it is stopped; the
// caller holds lifecycle.
func liveGranter() *store.PossessionGranter {
	if active == nil || active.granter == nil {
		return nil
	}
	return active.granter()
}
