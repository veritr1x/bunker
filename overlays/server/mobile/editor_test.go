package mobile

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"lunar-tear/server/internal/store"
)

// Pod Programs › Gift asks how much of a thing can still be claimed on every
// pick, with the game playing: that read is let through while the server
// runs. Anything that writes the save still needs the server stopped.
func TestEditWhileTheServerRuns(t *testing.T) {
	lifecycle.Lock()
	saved := active
	active = &instance{}
	lifecycle.Unlock()
	t.Cleanup(func() { lifecycle.Lock(); active = saved; lifecycle.Unlock() })
	dir := t.TempDir()
	if got := Edit(dir, dir, `{"action":"grant_possession","user_id":1}`); !strings.Contains(got, "Stop the game server") {
		t.Fatalf("a write while the server runs: %s", got)
	}
	if got := Edit(dir, dir, `{"action":"gift_room","user_id":1}`); strings.Contains(got, "Stop the game server") {
		t.Fatalf("the gift room read was refused: %s", got)
	}
	// Deck Builder's matching list only reads the save too.
	if got := Edit(dir, dir, `{"action":"arena_matching","user_id":1}`); strings.Contains(got, "Stop the game server") {
		t.Fatalf("the matching list read was refused: %s", got)
	}
}

// Deck Builder builds fully raised pieces on its own staging save, never the
// player's; a path in the request is never used. Building it loads the master
// data, which the running server reads too, so it waits for the server to be
// stopped (Pod Programs' game guard pauses it for the build).
func TestEditDeckBuilderStage(t *testing.T) {
	dir := t.TempDir()
	elsewhere := filepath.Join(t.TempDir(), "elsewhere.db")
	got := Edit(dir, dir, `{"target":"deckbuilder_stage","action":"stage_new","user_id":1,"db_path":"`+elsewhere+`"}`)
	if !strings.Contains(got, `"ok":true`) {
		t.Fatalf("stage_new: %s", got)
	}
	if _, err := os.Stat(filepath.Join(dir, "deckbuilder", "stage.db")); err != nil {
		t.Fatalf("no staging save: %v", err)
	}
	for _, p := range []string{filepath.Join(dir, "game.db"), elsewhere} {
		if _, err := os.Stat(p); !os.IsNotExist(err) {
			t.Fatalf("%s was touched", p)
		}
	}
	// Only the actions the stage is built with.
	for _, action := range []string{"deck_write", "send_gift", "grant_possession"} {
		if got := Edit(dir, dir, `{"target":"deckbuilder_stage","action":"`+action+`","user_id":1}`); !strings.Contains(got, "not a stage action") {
			t.Fatalf("%s on the stage: %s", action, got)
		}
	}
	// Per-costume karma (Deck Builder's bake picks each costume's best) is one of them.
	if got := Edit(dir, dir, `{"target":"deckbuilder_stage","action":"set_costume_karma_batch","user_id":1}`); strings.Contains(got, "not a stage action") {
		t.Fatalf("set_costume_karma_batch on the stage: %s", got)
	}
	// So is the characters' rank ("All maxed" is rank 10).
	if got := Edit(dir, dir, `{"target":"deckbuilder_stage","action":"rank_characters","user_id":1}`); strings.Contains(got, "not a stage action") {
		t.Fatalf("rank_characters on the stage: %s", got)
	}
	// And grants (the stained glass every fully progressed account owns).
	if got := Edit(dir, dir, `{"target":"deckbuilder_stage","action":"grant_batch","user_id":1}`); strings.Contains(got, "not a stage action") {
		t.Fatalf("grant_batch on the stage: %s", got)
	}
	// Any other target is refused.
	if got := Edit(dir, dir, `{"target":"other","action":"upgrade_all_memoirs","user_id":1}`); !strings.Contains(got, "Unknown save target") {
		t.Fatalf("unknown target: %s", got)
	}
	// While the server runs: refused, so the master data is never loaded under it.
	lifecycle.Lock()
	saved := active
	active = &instance{}
	lifecycle.Unlock()
	t.Cleanup(func() { lifecycle.Lock(); active = saved; lifecycle.Unlock() })
	if got := Edit(dir, dir, `{"target":"deckbuilder_stage","action":"upgrade_all_memoirs","user_id":1}`); !strings.Contains(got, "Stop the game server") {
		t.Fatalf("a stage edit ran beside the server: %s", got)
	}
}

// The stage path the action gets is the app's own, even when the request names one.
func TestEditStageIgnoresARequestedStagePath(t *testing.T) {
	got := stageRequest(t.TempDir(), "/master.bin.e", map[string]any{"action": "upgrade_all_memoirs", "stage_path": "/else.db", "db_path": "/else.db"})
	if got["stage_path"] != nil || !strings.HasSuffix(got["db_path"].(string), filepath.Join("deckbuilder", "stage.db")) {
		t.Fatalf("stage request: %v", got)
	}
}

// A deck write reads Deck Builder's own stage: a stage_path in the request is
// replaced with the app's, never used.
func TestEditFixesTheStagePath(t *testing.T) {
	got := editRequest(t.TempDir(), map[string]any{"action": "deck_write", "stage_path": "/somewhere/else.db"})
	if !strings.HasSuffix(got["stage_path"].(string), filepath.Join("deckbuilder", "stage.db")) {
		t.Fatalf("stage_path %v", got["stage_path"])
	}
}

// While the server runs, the shim checks gifts with the running server's
// granter (lunarbase.LiveGranter), never loading the master data again.
func TestTheShimUsesTheLiveGranter(t *testing.T) {
	lifecycle.Lock()
	saved := active
	g := &store.PossessionGranter{}
	active = &instance{granter: func() *store.PossessionGranter { return g }}
	lifecycle.Unlock()
	t.Cleanup(func() { lifecycle.Lock(); active = saved; lifecycle.Unlock() })
	if got := liveGranter(); got != g {
		t.Fatalf("granter %p, want the server's", got)
	}
	lifecycle.Lock()
	active = nil
	lifecycle.Unlock()
	if got := liveGranter(); got != nil {
		t.Fatal("a granter with no server running")
	}
}
