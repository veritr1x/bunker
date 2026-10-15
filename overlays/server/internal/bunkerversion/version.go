// Package bunkerversion holds Bunker's version, set when building with
// -ldflags "-X lunar-tear/server/internal/bunkerversion.Version=1.0.0".
package bunkerversion

// Version is "dev" in builds that don't set it.
var Version = "dev"
