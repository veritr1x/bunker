package main

import (
	"bufio"
	"bytes"
	"io"
	"os"
	"regexp"
	"strings"
	"sync"
	"testing"
	"time"
)

var ansi = regexp.MustCompile(`\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07`)

func TestPanelLive(t *testing.T) {
	var out bytes.Buffer
	p := newPanel(&out, true, "1.2.0")
	s := newSteps(p)
	p.set(s.adb, good, "READY", "37.0.1")
	p.set(s.image, busy, "DOWNLOADING", "")
	s.image.since = time.Now().Add(-time.Minute)
	p.progress(s.image, 600<<20, 1800<<20, "")
	p.say("Downloading x86_64-36_r07.zip from Google.")
	p.close()
	frames := strings.Split(out.String(), "\x1b[H")
	frame := ansi.ReplaceAllString(frames[len(frames)-1], "")
	t.Log("\n" + frame)
	for _, want := range []string{
		"LUNAR TEAR // WINDOWS", "B U N K E R", "1.2.0",
		"[ 01 EMULATOR ] ───", "[ 05 DEPLOY ]",
		"ADB              READY        37.0.1",
		"EMULATOR         STANDING BY",
		"▓▓▓▓░░░░░░░░  33% · 600 MB of 1.8 GB · 2 min left",
		"> Downloading x86_64-36_r07.zip from Google.",
	} {
		if !strings.Contains(frame, want) {
			t.Errorf("screen lacks %q", want)
		}
	}
}

func TestPanelPlain(t *testing.T) {
	var out bytes.Buffer
	p := newPanel(&out, false, "1.2.0")
	s := newSteps(p)
	p.set(s.files, busy, "STREAMING", "")
	for done := int64(0); done <= 100; done++ {
		p.progress(s.files, done, 100, "")
	}
	p.set(s.files, good, "IN PLACE", "201073 files")
	p.say("Done.")
	p.close()
	got := out.String()
	if strings.Contains(got, "\x1b") {
		t.Error("plain output has escape codes")
	}
	lines := strings.Split(strings.TrimSpace(got), "\n")
	// One line per status, one per 10% of progress, and the note.
	if len(lines) != 14 || lines[0] != "[04 GAME FILES] UNPACK: STREAMING" ||
		lines[12] != "[04 GAME FILES] UNPACK: IN PLACE · 201073 files" || lines[13] != "> Done." {
		t.Fatalf("plain output:\n%s", got)
	}
}

// The cards redraw every second; while a question waits, they must not draw
// over it (they did, so the first question vanished at once).
func TestQuestionStaysOnScreen(t *testing.T) {
	var out syncBuffer
	p := newPanel(&out, true, "1.2.0")
	s := newSteps(p)
	r, w := io.Pipe()
	stdin = bufio.NewReader(r)
	defer func() { stdin = bufio.NewReader(os.Stdin) }()
	go func() {
		time.Sleep(2500 * time.Millisecond)
		w.Write([]byte("C:\\bunker.apk\n"))
	}()
	p.set(s.install, busy, "NEEDS FILE", "bunker.apk")
	answer := p.ask("Bunker needs bunker.apk.", "Drag bunker.apk into this window and press Enter:")
	p.close()
	if answer != "C:\\bunker.apk" {
		t.Fatalf("answer %q", answer)
	}
	text := out.String()
	q := strings.Index(text, "Drag bunker.apk into this window")
	after := text[q:]
	// The next repaint must come after the answer clears the screen.
	redraw, cleared := strings.Index(after, "\x1b[H"), strings.Index(after, "\x1b[2J")
	if redraw >= 0 && (cleared < 0 || redraw < cleared) {
		t.Fatal("the screen was redrawn while the question waited")
	}
	before := ansi.ReplaceAllString(text[:q], "")
	frames := strings.Split(before, "\n")
	if !strings.Contains(before, "> Bunker needs bunker.apk.") || !strings.Contains(before, "NEEDS FILE") {
		t.Fatalf("the question's explanation or step is missing:\n%s", strings.Join(frames, "\n"))
	}
}

type syncBuffer struct {
	mu sync.Mutex
	b  bytes.Buffer
}

func (s *syncBuffer) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.b.Write(p)
}

func (s *syncBuffer) String() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.b.String()
}

func TestPhoneMemory(t *testing.T) {
	for host, want := range map[int]int{64 << 10: 8192, 16 << 10: 6144, 8 << 10: 4096, 0: 6144} {
		if got := phoneMemoryMB(host); got != want {
			t.Errorf("phoneMemoryMB(%d) = %d, want %d", host, got, want)
		}
	}
	if hostMemoryMB() <= 0 {
		t.Error("cannot read this computer's memory")
	}
}

func TestAccelName(t *testing.T) {
	if got := accelName("accel:\n0\nWHPX(10.0.26300) is installed and usable.\naccel\n"); got != "WHPX" {
		t.Fatalf("accelName = %q", got)
	}
	if got := accelName("accel:\n0\nHypervisor.Framework OS X Version 15.5 is installed and usable.\n"); got != "Hypervisor.Framework" {
		t.Fatalf("accelName = %q", got)
	}
}
