package mobile

import (
	"runtime/debug"
	"sync"
	"time"
)

// The server shares the phone with the game (on iOS, the game's own process), so
// it keeps its heap close to what it holds instead of Go's default of twice that,
// and returns freed memory to the system instead of keeping its peak.
const (
	gcPercent = 50
	// memoryLimit makes Go collect harder as its memory nears this. Imports and the
	// Archive's 3D models can briefly need more, and then get it.
	memoryLimit = 128 << 20
	// releaseDelay is how long after the last large job (an Archive conversion, an
	// import) the freed memory is returned, so a run of them pays for it once.
	releaseDelay = 2 * time.Second
)

func init() {
	debug.SetGCPercent(gcPercent)
	debug.SetMemoryLimit(memoryLimit)
}

var (
	releaseMu    sync.Mutex
	releaseTimer *time.Timer
)

// releaseMemory collects now and returns freed memory to the system.
func releaseMemory() { debug.FreeOSMemory() }

// releaseMemorySoon returns freed memory once no large job has run for releaseDelay.
func releaseMemorySoon() {
	releaseMu.Lock()
	defer releaseMu.Unlock()
	if releaseTimer == nil {
		releaseTimer = time.AfterFunc(releaseDelay, releaseMemory)
	} else {
		releaseTimer.Reset(releaseDelay)
	}
}
