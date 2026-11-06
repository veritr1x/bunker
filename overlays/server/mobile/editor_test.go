package mobile

import (
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
