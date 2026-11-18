// bunker-server runs Bunker's Lunar Tear server on a computer, for a game that
// runs there too. It serves the same three loopback ports as the phone build:
// game (8003), assets (8080) and accounts (3000), each plus -port-offset.
//
//	bunker-server -data <save directory> -assets <game files directory>
//
// "bunker-server import" puts the game files in place first (import.go).
// "bunker-server saves" exports and imports save backups (saves.go).
// With -control it also serves a loopback endpoint for Pod Programs (control.go).
//
// It runs until it is interrupted, or until its standard input closes when
// -stdin is given (a launcher that exits then takes the server with it).
package main

import (
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"

	"lunar-tear/server/mobile"
)

func main() {
	if len(os.Args) > 1 && os.Args[1] == "import" {
		importCommand(os.Args[2:])
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "saves" {
		savesCommand(os.Args[2:])
		return
	}
	data := flag.String("data", "", "directory for saves and server state (created if missing)")
	assets := flag.String("assets", "", "directory holding the imported game files")
	offset := flag.Int("port-offset", 0, "added to each port: 8003 game, 8080 assets, 3000 accounts")
	backups := flag.String("backups", "", "directory for the save snapshot taken before a new version first opens a save (default: backups inside -data)")
	stdin := flag.Bool("stdin", false, "stop when standard input closes")
	check := flag.Bool("self-test", false, "after starting, check that each service answers, then report")
	control := flag.String("control", "", "also serve the control endpoint Pod Programs uses, on this loopback address (such as 127.0.0.1:0); the token is read from BUNKER_CONTROL_TOKEN")
	flag.Parse()
	if *data == "" || *assets == "" || flag.NArg() != 0 {
		flag.Usage()
		os.Exit(2)
	}
	if e := os.MkdirAll(*data, 0o755); e != nil {
		fail(e.Error())
	}
	// A save made by another version is copied here before this one updates it;
	// without a folder the server refuses such a save.
	if *backups == "" {
		*backups = filepath.Join(*data, "backups")
	}
	mobile.SetBackupDir(*backups)
	if e := mobile.SetPortOffset(*offset); e != "" {
		fail(e)
	}
	if e := mobile.Start(*data, *assets); e != nil {
		fail(e.Error())
	}
	fmt.Println(mobile.Ports())
	if *control != "" {
		token := os.Getenv("BUNKER_CONTROL_TOKEN")
		if len(token) < 16 {
			fail("-control needs BUNKER_CONTROL_TOKEN, at least 16 characters")
		}
		url, e := serveControl(*control, token, *data, *assets)
		if e != nil {
			fail(e.Error())
		}
		fmt.Printf("{\"control\":%q}\n", url)
	}
	if *check {
		fmt.Println(mobile.SelfTest())
	}
	done := make(chan struct{}, 2)
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, os.Interrupt, syscall.SIGTERM)
	go func() { <-signals; done <- struct{}{} }()
	if *stdin {
		go func() { io.Copy(io.Discard, os.Stdin); done <- struct{}{} }()
	}
	<-done
	mobile.Stop()
}

func fail(message string) {
	fmt.Fprintln(os.Stderr, "bunker-server: "+message)
	os.Exit(1)
}
