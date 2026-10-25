package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

// The console looks like the Bunker's own screen: a card per stage, a row per
// step, and a status that changes in place. Where the output is not a console
// (a log file, a pipe), each change is written as a plain line instead.

type tone int

const (
	idle tone = iota
	busy
	good
	bad
)

type row struct {
	section, label string
	tone           tone
	status, detail string
	since          time.Time // when it became busy, for the running time
	fraction       float64   // progress, or -1
}

type panel struct {
	mu       sync.Mutex
	out      io.Writer
	live     bool
	title    string
	rows     []*row
	note     string
	drawn    time.Time
	stop     chan struct{}
	stopped  sync.WaitGroup
	lastPlan map[*row]string // plain mode: the last line written for each row
}

func newPanel(out io.Writer, live bool, title string) *panel {
	p := &panel{out: out, live: live, title: title, stop: make(chan struct{}), lastPlan: map[*row]string{}}
	if live {
		fmt.Fprint(out, "\x1b]0;Bunker\x07\x1b[?25l\x1b[2J")
		// Running times and progress tick even when nothing reports.
		p.stopped.Add(1)
		go func() {
			defer p.stopped.Done()
			for {
				select {
				case <-p.stop:
					return
				case <-time.After(time.Second):
					p.mu.Lock()
					p.draw()
					p.mu.Unlock()
				}
			}
		}()
	}
	return p
}

// add puts a step under a section, standing by.
func (p *panel) add(section, label string) *row {
	r := &row{section: section, label: label, status: "STANDING BY", fraction: -1}
	p.rows = append(p.rows, r)
	return r
}

// set changes a step's status and redraws.
func (p *panel) set(r *row, t tone, status, detail string) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if t == busy && (r.tone != busy || r.status != status) {
		r.since = time.Now()
	}
	r.tone, r.status, r.detail, r.fraction = t, status, detail, -1
	p.changed(r, true)
}

// progress shows how far a busy step is, with the time left once it can tell.
func (p *panel) progress(r *row, done, total int64, unit string) {
	if total <= 0 {
		return
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	r.fraction = float64(done) / float64(total)
	detail := fmt.Sprintf("%d%% · %s", int(r.fraction*100), amount(done, total, unit))
	if elapsed := time.Since(r.since); elapsed > 10*time.Second && done > 0 && done < total {
		left := time.Duration(float64(elapsed) * float64(total-done) / float64(done))
		detail += " · " + roughly(left) + " left"
	}
	r.detail = detail
	p.changed(r, time.Since(p.drawn) > 250*time.Millisecond)
}

// say sets the line under the cards: what is happening, or what to do.
func (p *panel) say(format string, args ...any) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.note = fmt.Sprintf(format, args...)
	if p.live {
		p.draw()
	} else {
		fmt.Fprintln(p.out, "> "+p.note)
	}
}

func (p *panel) changed(r *row, now bool) {
	if p.live {
		if now {
			p.draw()
		}
		return
	}
	line := fmt.Sprintf("[%s] %s: %s", r.section, r.label, r.status)
	if r.detail != "" && r.fraction < 0 {
		line += " · " + r.detail
	}
	if r.fraction >= 0 {
		line += fmt.Sprintf(" %d%%", int(r.fraction*10)*10) // every 10%
	}
	if p.lastPlan[r] != line {
		p.lastPlan[r] = line
		fmt.Fprintln(p.out, line)
	}
}

// ask shows a question over the cards and returns the answer. The text, such as
// a license, may be long; the cards come back once it is answered.
func (p *panel) ask(text, question string) string {
	p.mu.Lock()
	if p.live {
		fmt.Fprint(p.out, "\x1b[2J\x1b[H\x1b[?25h")
	}
	if text != "" {
		fmt.Fprintln(p.out, text)
		fmt.Fprintln(p.out)
	}
	fmt.Fprint(p.out, question+" ")
	p.mu.Unlock()
	answer, _ := stdin.ReadString('\n')
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.live {
		fmt.Fprint(p.out, "\x1b[?25l\x1b[2J")
		p.draw()
	} else {
		fmt.Fprintln(p.out)
	}
	return strings.TrimSpace(answer)
}

// close stops the ticking and leaves the final screen in place.
func (p *panel) close() {
	close(p.stop)
	p.stopped.Wait()
	if p.live {
		p.mu.Lock()
		p.draw()
		p.mu.Unlock()
		fmt.Fprint(p.out, "\x1b[?25h")
	}
}

const (
	reset  = "\x1b[0m"
	dim    = "\x1b[90m"
	bold   = "\x1b[1m"
	yellow = "\x1b[33m"
	green  = "\x1b[32m"
	red    = "\x1b[31m"
	width  = 56
)

// draw repaints the whole screen from the top. The caller holds p.mu.
func (p *panel) draw() {
	p.drawn = time.Now()
	var b strings.Builder
	b.WriteString("\x1b[H")
	line := func(s string) { b.WriteString(s + "\x1b[K\n") }
	// About 20 lines, to fit a console window's default height.
	line(dim + "  LUNAR TEAR // WINDOWS" + reset)
	line(bold + "  B U N K E R" + reset + strings.Repeat(" ", max(1, width-13-len(p.title))) + dim + p.title + reset)
	line("")
	section := ""
	for _, r := range p.rows {
		if r.section != section {
			section = r.section
			head := "[ " + section + " ] "
			line(bold + "  " + head + reset + dim + strings.Repeat("─", max(0, width-utf8.RuneCountInString(head))) + reset)
		}
		color := map[tone]string{idle: dim, busy: yellow, good: green, bad: red}[r.tone]
		detail := r.detail
		if r.tone == busy && r.fraction < 0 && detail == "" {
			detail = clock(time.Since(r.since))
		}
		if r.fraction >= 0 {
			filled := int(r.fraction * 12)
			detail = yellow + strings.Repeat("▓", filled) + dim + strings.Repeat("░", 12-filled) + reset + "  " + detail
		}
		line(fmt.Sprintf("    %-16s %s%-12s%s %s", r.label, color, r.status, reset, detail))
	}
	line("")
	prefix := bold + "> " + reset
	for _, l := range strings.Split(p.note, "\n") {
		for _, part := range wrap(l, width+18) {
			if p.note != "" {
				line("  " + prefix + part)
				prefix = "  "
			}
		}
	}
	b.WriteString("\x1b[J")
	fmt.Fprint(p.out, b.String())
}

// amount is "341 of 434 MB", "1.5 of 1.8 GB" or "600 MB of 1.8 GB".
func amount(done, total int64, unit string) string {
	if unit == "files" {
		return fmt.Sprintf("%d of %d files", done, total)
	}
	d, du := size(done)
	t, tu := size(total)
	if du == tu {
		return d + " of " + t + " " + tu
	}
	return d + " " + du + " of " + t + " " + tu
}

func size(n int64) (string, string) {
	if n >= 1<<30 {
		return fmt.Sprintf("%.1f", float64(n)/(1<<30)), "GB"
	}
	return fmt.Sprintf("%d", n>>20), "MB"
}

func clock(d time.Duration) string {
	s := int(d.Seconds())
	return fmt.Sprintf("%d:%02d", s/60, s%60)
}

func roughly(d time.Duration) string {
	if d < time.Minute {
		return "<1 min"
	}
	return fmt.Sprintf("%d min", int(d.Minutes()+0.5))
}

// wrap breaks a line at spaces so it fits n columns.
func wrap(s string, n int) []string {
	var out []string
	for utf8.RuneCountInString(s) > n {
		cut := strings.LastIndex(s[:n], " ")
		if cut <= 0 {
			break
		}
		out = append(out, s[:cut])
		s = s[cut+1:]
	}
	return append(out, s)
}

// askPath asks for a file, which can be dragged into the console window: that
// types its path, in quotes when it has spaces.
func (p *panel) askPath(text, question string) string {
	answer := strings.Trim(p.ask(text, question), "\"' ")
	if answer == "" {
		return ""
	}
	if _, err := os.Stat(answer); err != nil {
		p.say("Cannot find %s.", answer)
		return ""
	}
	return answer
}

var stdin = bufio.NewReader(os.Stdin)
