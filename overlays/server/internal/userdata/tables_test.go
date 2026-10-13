package userdata

import (
	"testing"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// The client's first load stops on a table sent as null; empty tables must be [].
func TestNoTableIsNull(t *testing.T) {
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	for name, js := range FullClientTableMap(*user) {
		if js == "null" || js == "" {
			t.Errorf("%s is %q", name, js)
		}
	}
}
