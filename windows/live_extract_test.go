package main

import (
	"errors"
	"os"
	"testing"
)

// Times the unpacking against a real dump, on the computer that will run it:
//
//	BUNKER_DUMP=resource_dump_android.7z BUNKER_DEST=D:\x go test -run LiveExtract
func TestLiveExtract(t *testing.T) {
	src, dest := os.Getenv("BUNKER_DUMP"), os.Getenv("BUNKER_DEST")
	if src == "" || dest == "" {
		t.Skip("set BUNKER_DUMP and BUNKER_DEST to unpack a real dump")
	}
	if err := extractGameFiles(src, dest); err != nil {
		t.Fatal(err)
	}
}

// Reads a real dump's index from a link and stops at the space check, before
// any game data is downloaded:
//
//	BUNKER_LINK=<link to the .7z> go test -run LiveLink -v
func TestLiveLink(t *testing.T) {
	link := os.Getenv("BUNKER_LINK")
	if link == "" {
		t.Skip("set BUNKER_LINK to read a real dump's index from a link")
	}
	stop := errors.New("stopped at the space check")
	var total int64
	_, err := unpackGameFiles(link, dirSink(t.TempDir()), func(n int64) error { total = n; return stop }, nil)
	if !errors.Is(err, stop) {
		t.Fatal(err)
	}
	t.Logf("revision 0 unpacks to %d bytes; with %d free the check says: %v", total, int64(4e9), enoughSpace(total, 4e9))
}
