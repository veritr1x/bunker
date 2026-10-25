package main

import (
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
