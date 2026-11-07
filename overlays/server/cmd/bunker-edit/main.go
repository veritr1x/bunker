// bunker-edit runs one Lunar Base save edit outside the app: Pod Programs ›
// Deck Builder's tests and desktop tools use it to build a staging save with
// the server's own grant and upgrade actions.
//
//	bunker-edit new-stage <path>     an empty save holding only player 1
//	bunker-edit < request.json       one action, as the Android bridge sends it
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"

	"lunar-tear/server/internal/lunarbase"
)

func main() {
	if len(os.Args) == 3 && os.Args[1] == "new-stage" {
		if err := lunarbase.NewStage(os.Args[2]); err != nil {
			reply(false, err.Error())
		}
		reply(true, "")
	}
	raw, err := io.ReadAll(os.Stdin)
	if err != nil {
		reply(false, err.Error())
	}
	out := lunarbase.Execute(raw)
	fmt.Println(out)
	var r struct {
		OK bool `json:"ok"`
	}
	if json.Unmarshal([]byte(out), &r) != nil || !r.OK {
		os.Exit(1)
	}
}

func reply(ok bool, message string) {
	b, _ := json.Marshal(map[string]any{"ok": ok, "error": message})
	fmt.Println(string(b))
	if ok {
		os.Exit(0)
	}
	os.Exit(1)
}
