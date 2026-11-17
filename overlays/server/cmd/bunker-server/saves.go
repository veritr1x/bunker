package main

import (
	"archive/zip"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"lunar-tear/server/mobile"
)

// bunker-server saves keeps and restores the player's save, in the format the
// phone app's Export save backup writes (a ZIP of game.db, auth.db and
// auth.key), so a save moves between a phone and a computer either way:
//
//	bunker-server saves export -data <save directory> -out <backup.zip>
//	bunker-server saves import -data <save directory> -from <backup.zip or game.db>
//
// Run them while the server is stopped. An import keeps the saves it replaces
// in <save directory>.before-import.
func savesCommand(arguments []string) {
	usage := func() {
		fmt.Fprintln(os.Stderr, "usage: bunker-server saves export -data <save directory> -out <backup.zip>\n"+
			"       bunker-server saves import -data <save directory> -from <backup.zip or game.db>")
		os.Exit(2)
	}
	if len(arguments) == 0 {
		usage()
	}
	flags := flag.NewFlagSet("saves "+arguments[0], flag.ExitOnError)
	data := flags.String("data", "", "the save directory the server is started with")
	out := flags.String("out", "", "the backup to write")
	from := flags.String("from", "", "the backup to restore")
	flags.Parse(arguments[1:])
	switch {
	case arguments[0] == "export" && *data != "" && *out != "":
		if e := exportSaves(*data, *out); e != nil {
			fail(e.Error())
		}
	case arguments[0] == "import" && *data != "" && *from != "":
		if e := os.MkdirAll(*data, 0o755); e != nil {
			fail(e.Error())
		}
		if problem := mobile.ImportSaves(*data, *from); problem != "" {
			fail(problem)
		}
	default:
		usage()
	}
}

func exportSaves(data, out string) error {
	if !exists(filepath.Join(data, "game.db")) {
		return fmt.Errorf("There is no save in %s yet.", data)
	}
	// Fold in what the server had not written into the database files yet.
	if problem := mobile.PrepareBackup(data); problem != "" {
		return fmt.Errorf("%s", problem)
	}
	temp := out + ".writing"
	file, e := os.Create(temp)
	if e != nil {
		return e
	}
	archive := zip.NewWriter(file)
	for _, name := range []string{"game.db", "auth.db", "auth.key"} {
		source, e := os.Open(filepath.Join(data, name))
		if os.IsNotExist(e) {
			continue
		}
		if e == nil {
			var entry io.Writer
			if entry, e = archive.Create(name); e == nil {
				_, e = io.Copy(entry, source)
			}
			source.Close()
		}
		if e != nil {
			file.Close()
			os.Remove(temp)
			return e
		}
	}
	e = archive.Close()
	if c := file.Close(); e == nil {
		e = c
	}
	if e != nil {
		os.Remove(temp)
		return e
	}
	return os.Rename(temp, out)
}
