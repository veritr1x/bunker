package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"

	"lunar-tear/server/mobile"
)

// bunker-server import puts the player's game files where the server reads them,
// as the launcher on a phone does:
//
//	bunker-server import -assets <game files directory> [-dump <resource dump>] [-master <master data>]
//
// -dump is the resource dump as a .7z or .zip. It is extracted beside the
// current files and swapped in only when it is complete, so a failed import
// leaves what was there. -master is the master data file
// (20240404193219.bin.e); it is checked before it replaces the current one.
// Progress is printed as one JSON object per line.
func importCommand(arguments []string) {
	flags := flag.NewFlagSet("import", flag.ExitOnError)
	root := flags.String("assets", "", "the game files directory the server is started with")
	dump := flags.String("dump", "", "the resource dump, a .7z or .zip")
	master := flags.String("master", "", "the master data file, 20240404193219.bin.e")
	flags.Parse(arguments)
	if *root == "" || (*dump == "" && *master == "") || flags.NArg() != 0 {
		flags.Usage()
		os.Exit(2)
	}
	if e := os.MkdirAll(*root, 0o755); e != nil {
		fail(e.Error())
	}
	assets := filepath.Join(*root, "assets")
	current := filepath.Join(assets, "release", mobile.MasterName)
	if *master != "" {
		say("master", 0, 0)
		if problem := mobile.CheckMaster(*master, filepath.Base(*master)); problem != "" {
			fail(problem)
		}
		if e := copyFile(*master, current); e != nil {
			fail(e.Error())
		}
	}
	if *dump != "" {
		if e := importDump(*root, assets, current, *dump); e != nil {
			fail(e.Error())
		}
	}
	say("done", 0, 0)
}

func importDump(root, assets, master, dump string) error {
	stage := filepath.Join(root, "assets.importing")
	old := filepath.Join(root, "assets.previous")
	os.RemoveAll(stage)
	defer os.RemoveAll(stage)
	finished := make(chan string, 1)
	go func() { finished <- mobile.ImportArchive(dump, stage) }()
	for waiting := true; waiting; {
		select {
		case problem := <-finished:
			if problem != "" {
				return errors.New(problem)
			}
			waiting = false
		case <-time.After(time.Second):
			var state struct{ Done, Total int64 }
			json.Unmarshal([]byte(mobile.ImportProgress()), &state)
			if state.Total > 0 {
				say("extracting", state.Done, state.Total)
			}
		}
	}
	say("finishing", 0, 0)
	if !exists(filepath.Join(stage, "revisions/0/android/list.bin")) && !exists(filepath.Join(stage, "revisions/0/list.bin")) {
		return errors.New("That archive holds no game file list (revisions/0). Choose the resource dump.")
	}
	// The master data and the calendar's next loop are kept across an import.
	for _, name := range []string{mobile.MasterName, "calendar-next.bin"} {
		from, to := filepath.Join(assets, "release", name), filepath.Join(stage, "release", name)
		if exists(from) && !exists(to) {
			if e := copyFile(from, to); e != nil {
				return e
			}
		}
	}
	os.RemoveAll(old)
	if exists(assets) {
		if e := os.Rename(assets, old); e != nil {
			return e
		}
	}
	if e := os.Rename(stage, assets); e != nil {
		if exists(old) {
			os.Rename(old, assets)
		}
		return e
	}
	return os.RemoveAll(old)
}

func say(step string, done, total int64) {
	b, _ := json.Marshal(map[string]any{"step": step, "done": done, "total": total})
	fmt.Println(string(b))
}

func exists(path string) bool { _, e := os.Stat(path); return e == nil }

// copyFile writes through a temporary name, so the target is whole or absent.
func copyFile(from, to string) error {
	if e := os.MkdirAll(filepath.Dir(to), 0o755); e != nil {
		return e
	}
	in, e := os.Open(from)
	if e != nil {
		return e
	}
	defer in.Close()
	temp := to + ".importing"
	out, e := os.Create(temp)
	if e != nil {
		return e
	}
	if _, e = io.Copy(out, in); e == nil {
		e = out.Sync()
	}
	if c := out.Close(); e == nil {
		e = c
	}
	if e != nil {
		os.Remove(temp)
		return e
	}
	return os.Rename(temp, to)
}
