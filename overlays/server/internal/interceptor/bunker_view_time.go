package interceptor

import "lunar-tear/server/internal/gametime"

// viewNowMillis is the clock the game is sent: in the original-dates view the
// calendar's offset behind (gametime.ViewOffset).
func viewNowMillis() int64 {
	return gametime.NowMillis() - gametime.ViewOffset()
}
