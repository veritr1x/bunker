package mobile

import (
	"strings"
	"testing"
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
