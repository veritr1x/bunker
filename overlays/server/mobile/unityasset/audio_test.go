package unityasset

import (
	"bytes"
	"encoding/binary"
	"hash/crc32"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSetupsMatchTheirCRC(t *testing.T) {
	for crc, s := range vorbisSetups {
		if got := crc32.ChecksumIEEE(s.setup); got != crc {
			t.Errorf("setup %d hashes to %d", crc, got)
		}
		if _, err := vorbisModes(s.setup, 2); err != nil {
			t.Errorf("setup %d: %v", crc, err)
		}
	}
}

type oggPacket struct {
	data    []byte
	granule int64 // of the page the packet ends on, or -1 when another packet ends there later
}

// readOgg splits an Ogg stream into packets, checking every page's CRC.
func readOgg(t *testing.T, data []byte) []oggPacket {
	var out []oggPacket
	var cur []byte
	for len(data) > 0 {
		if len(data) < 27 || string(data[:4]) != "OggS" {
			t.Fatal("bad page")
		}
		n := int(data[26])
		segs := data[27 : 27+n]
		size := 0
		for _, s := range segs {
			size += int(s)
		}
		page := data[:27+n+size]
		check := bytes.Clone(page)
		binary.LittleEndian.PutUint32(check[22:], 0)
		var crc uint32
		for _, b := range check {
			crc = crc<<8 ^ oggCRC[byte(crc>>24)^b]
		}
		if crc != binary.LittleEndian.Uint32(page[22:]) {
			t.Fatal("page CRC mismatch")
		}
		granule := int64(binary.LittleEndian.Uint64(page[6:]))
		body := page[27+n:]
		ended := []int{}
		for _, s := range segs {
			cur = append(cur, body[:s]...)
			body = body[s:]
			if s < 255 {
				out = append(out, oggPacket{data: cur, granule: -1})
				ended = append(ended, len(out)-1)
				cur = nil
			}
		}
		if len(ended) > 0 {
			out[ended[len(ended)-1]].granule = granule
		}
		data = data[len(page):]
	}
	return out
}

// TestOggMatchesTheReference rebuilds real clips and compares them with python-fsb5's
// output (libvorbis): the same audio packets, and the same granule positions where both
// streams end a page. Set ARCHIVE_DUMP and ARCHIVE_AUDIO_REFS (reference .ogg files named
// like voice__en__main__…__mid_a000_0040_00100_01010_1.ogg).
func TestOggMatchesTheReference(t *testing.T) {
	dump, refs := os.Getenv("ARCHIVE_DUMP"), os.Getenv("ARCHIVE_AUDIO_REFS")
	if dump == "" || refs == "" {
		t.Skip("set ARCHIVE_DUMP and ARCHIVE_AUDIO_REFS")
	}
	files, _ := filepath.Glob(filepath.Join(refs, "*.ogg"))
	if len(files) == 0 {
		t.Fatal("no reference .ogg files")
	}
	for _, ref := range files {
		name := strings.TrimSuffix(filepath.Base(ref), ".ogg")
		t.Run(name, func(t *testing.T) {
			out := filepath.Join(t.TempDir(), "out.ogg")
			if err := AudioToOgg(filepath.Join(dump, "assetbundle", strings.ReplaceAll(name, "__", "/")+".assetbundle"), out); err != nil {
				t.Fatal(err)
			}
			mine, _ := os.ReadFile(out)
			theirs, _ := os.ReadFile(ref)
			got, want := readOgg(t, mine), readOgg(t, theirs)
			if len(got) != len(want) {
				t.Fatalf("%d packets, want %d", len(got), len(want))
			}
			for i := range want {
				if i == 1 { // comment header: our own vendor string
					continue
				}
				if !bytes.Equal(got[i].data, want[i].data) {
					t.Fatalf("packet %d differs", i)
				}
			}
			ours := map[int]int64{}
			for i, p := range got {
				if p.granule >= 0 {
					ours[i] = p.granule
				}
			}
			// Granule of a packet in our stream: recompute from each page end we know.
			for i, p := range want {
				if g, ok := ours[i]; ok && p.granule >= 0 && g != p.granule {
					t.Fatalf("packet %d granule %d, want %d", i, g, p.granule)
				}
			}
			if got[len(got)-1].granule != want[len(want)-1].granule {
				t.Fatalf("final granule %d, want %d", got[len(got)-1].granule, want[len(want)-1].granule)
			}
		})
	}
}
