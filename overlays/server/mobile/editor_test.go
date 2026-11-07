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
}

// Deck Builder builds fully raised pieces on its own staging save: those edits
// never reach the player's save, so they are let through while the game runs,
// and a path in the request is never used.
func TestEditDeckBuilderStage(t *testing.T) {
	lifecycle.Lock()
	saved := active
	active = &instance{}
	lifecycle.Unlock()
	t.Cleanup(func() { lifecycle.Lock(); active = saved; lifecycle.Unlock() })
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
	// An ordinary action on the stage runs while the server does.
	if got := Edit(dir, dir, `{"target":"deckbuilder_stage","action":"upgrade_all_memoirs","user_id":1}`); strings.Contains(got, "Stop the game server") {
		t.Fatalf("a stage edit was refused while the server runs: %s", got)
	}
	// Any other target is refused.
	if got := Edit(dir, dir, `{"target":"other","action":"upgrade_all_memoirs","user_id":1}`); !strings.Contains(got, "Unknown save target") {
		t.Fatalf("unknown target: %s", got)
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
