// Package remotefile reads a file on a web server by position, as an
// io.ReaderAt, with HTTP range requests. An archive can then be unpacked
// straight from a link, fetching only the parts that are read, and never
// stored whole.
//
// Links to archive.org, Google Drive and Mega are worked out to their files
// (hosts.go, mega.go); any other server must accept range requests.
//
// This package uses only the standard library. The same files live in
// overlays/server/mobile/remotefile and windows/remotefile, and a test in
// windows/ fails when they differ.
package remotefile

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"path"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// ErrNoRanges is returned by Open for a server that cannot send part of a file.
var ErrNoRanges = errors.New("This server does not allow resuming downloads, so Bunker cannot read the archive from it. Download the file and choose it as an archive instead.")

// Retries: the wait starts at retryFirst and doubles up to retryMax; a read
// gives up once retryGiveUp passes without any data arriving.
var (
	retryFirst  = time.Second
	retryMax    = 30 * time.Second
	retryGiveUp = 5 * time.Minute
)

const (
	chunkSize   = 1 << 20  // the cache's unit, for small scattered reads such as the index
	cacheChunks = 16       // chunks kept
	smallRead   = 64 << 10 // reads up to this size may go through the cache
	maxStreams  = 8        // sequential readers kept
	skipAhead   = 8 << 20  // a stream this close behind a read moves forward instead of starting over
	// A stream fetches segmentSize pieces, aheadSegments of them at once:
	// hosts such as archive.org send each connection about 1 MB/s.
	segmentSize   = 4 << 20
	aheadSegments = 4
)

// IsLink reports whether s is an http or https URL rather than a file path.
func IsLink(s string) bool {
	l := strings.ToLower(strings.TrimSpace(s))
	return strings.HasPrefix(l, "http://") || strings.HasPrefix(l, "https://")
}

// source is what a resolver works out from a link.
type source struct {
	urls []string // tried in order when one fails with a server or network error
	size int64
	id   string // stable for the same file: the host's file id and the size
	name string
	host string // "archive.org", "drive", "mega" or "http"
	// decrypt, if set, turns the bytes read at off into plaintext in place.
	decrypt func(p []byte, off int64)
	// refresh, if set, gets a new URL when the current one is refused (Mega's
	// download URLs expire).
	refresh func(ctx context.Context) (string, error)
	// explain, if set, turns an HTTP status into a message for the player, or nil.
	explain func(code int) error
}

// File is a remote file read by position. ReadAt is safe for concurrent use.
type File struct {
	ctx    context.Context
	client *http.Client
	src    source

	stop context.CancelFunc

	mu      sync.Mutex
	current int       // index into src.urls of the URL in use
	streams []*stream // idle sequential readers, least recently used first
	cache   map[int64][]byte
	order   []int64 // cache keys, oldest first

	received atomic.Int64
	closed   atomic.Bool
}

// stream reads a file onward from off, fetching the next segments at once.
type stream struct {
	off   int64      // the next byte to hand out
	queue []*segment // fetched or being fetched, in order, from off's segment
	next  int64      // where the next segment to fetch starts
}

type segment struct {
	start int64
	data  []byte
	err   error
	done  chan struct{}
}

// Open works out rawURL and checks that its server can send parts of the
// file. ctx cancels every later read too. client may be nil.
func Open(ctx context.Context, rawURL string, client *http.Client) (*File, error) {
	if client == nil {
		client = newClient()
	}
	u, err := url.Parse(strings.TrimSpace(rawURL))
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		return nil, errors.New("Paste a link that starts with http:// or https://")
	}
	src, err := resolve(ctx, client, u)
	if err != nil {
		return nil, err
	}
	ctx, stop := context.WithCancel(ctx)
	return &File{ctx: ctx, stop: stop, client: client, src: src, cache: map[int64][]byte{}}, nil
}

// newClient waits up to 30 s to connect and for headers, and has no overall
// limit, since one response may stream for an hour.
func newClient() *http.Client {
	t := http.DefaultTransport.(*http.Transport).Clone()
	t.DialContext = (&net.Dialer{Timeout: 30 * time.Second, KeepAlive: 30 * time.Second}).DialContext
	t.ResponseHeaderTimeout = 30 * time.Second
	t.TLSHandshakeTimeout = 30 * time.Second
	return &http.Client{Transport: t}
}

func (f *File) Size() int64 { return f.src.size }

// Name is the file's name, from the link or the host.
func (f *File) Name() string { return f.src.name }

// ID identifies the file for resuming: the same file from the same host has the same ID.
func (f *File) ID() string { return f.src.id }

// Host is "archive.org", "drive", "mega" or "http".
func (f *File) Host() string { return f.src.host }

// Received counts the bytes downloaded so far.
func (f *File) Received() int64 { return f.received.Load() }

// Close stops any fetches still running.
func (f *File) Close() error {
	f.closed.Store(true)
	f.stop()
	f.mu.Lock()
	defer f.mu.Unlock()
	f.streams = nil
	return nil
}

// ReadAt reads len(p) bytes at off, retrying through dropped connections.
func (f *File) ReadAt(p []byte, off int64) (int, error) {
	if off < 0 {
		return 0, errors.New("remotefile: negative offset")
	}
	if off >= f.src.size {
		return 0, io.EOF
	}
	want := p
	if rest := f.src.size - off; int64(len(p)) > rest {
		want = p[:rest]
	}
	n := 0
	for n < len(want) {
		m, err := f.readSome(want[n:], off+int64(n))
		n += m
		if err != nil {
			return n, err
		}
	}
	if len(want) < len(p) {
		return n, io.EOF
	}
	return n, nil
}

// readSome reads at least one byte of p at off: from the cache, an open
// stream, a new cached chunk, or a new stream.
func (f *File) readSome(p []byte, off int64) (int, error) {
	if n := f.fromCache(p, off); n > 0 {
		return n, nil
	}
	if st := f.takeStream(off); st != nil {
		return f.fromStream(st, p, off)
	}
	key := off / chunkSize * chunkSize
	f.mu.Lock()
	_, sequential := f.cache[key-chunkSize]
	f.mu.Unlock()
	if len(p) <= smallRead && !sequential {
		if err := f.fetchChunk(key); err != nil {
			return 0, err
		}
		return f.fromCache(p, off), nil
	}
	// A large read, or small reads that went on past a cached chunk: stream.
	return f.fromStream(&stream{off: off, next: off}, p, off)
}

func (f *File) fromCache(p []byte, off int64) int {
	key := off / chunkSize * chunkSize
	f.mu.Lock()
	defer f.mu.Unlock()
	chunk, ok := f.cache[key]
	if !ok || off-key >= int64(len(chunk)) {
		return 0
	}
	return copy(p, chunk[off-key:])
}

func (f *File) fetchChunk(key int64) error {
	end := min(key+chunkSize, f.src.size) - 1
	chunk := make([]byte, end-key+1)
	err := f.retry(func(progress func()) error {
		resp, err := f.get(key, end)
		if err != nil {
			return err
		}
		defer resp.Body.Close()
		_, err = io.ReadFull(&counted{resp.Body, f, progress}, chunk)
		return err
	})
	if err != nil {
		return err
	}
	if f.src.decrypt != nil {
		f.src.decrypt(chunk, key)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, ok := f.cache[key]; !ok {
		f.cache[key] = chunk
		f.order = append(f.order, key)
		if len(f.order) > cacheChunks {
			delete(f.cache, f.order[0])
			f.order = f.order[1:]
		}
	}
	return nil
}

// takeStream removes from the pool a stream at off or a little before it.
func (f *File) takeStream(off int64) *stream {
	f.mu.Lock()
	defer f.mu.Unlock()
	for i := len(f.streams) - 1; i >= 0; i-- {
		st := f.streams[i]
		if st.off <= off && off-st.off < skipAhead {
			f.streams = append(f.streams[:i], f.streams[i+1:]...)
			return st
		}
	}
	return nil
}

func (f *File) putStream(st *stream) {
	if f.closed.Load() {
		return
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	f.streams = append(f.streams, st)
	if len(f.streams) > maxStreams {
		f.streams = f.streams[1:] // its fetches finish and are dropped
	}
}

// fromStream fills p with the bytes at off from st's segments, keeping
// aheadSegments of them fetching.
func (f *File) fromStream(st *stream, p []byte, off int64) (int, error) {
	st.off = off
	n := 0
	for n < len(p) {
		// Drop segments behind the read, then keep the queue full.
		for len(st.queue) > 0 && st.queue[0].start+segmentSize <= st.off {
			st.queue = st.queue[1:]
		}
		if len(st.queue) == 0 {
			st.next = st.off
		}
		for len(st.queue) < aheadSegments && st.next < f.src.size {
			st.queue = append(st.queue, f.fetchSegment(st.next))
			st.next += segmentSize
		}
		seg := st.queue[0]
		select {
		case <-seg.done:
		case <-f.ctx.Done():
			return n, f.ctx.Err()
		}
		if seg.err != nil {
			return n, seg.err // a later read starts this stream again
		}
		m := copy(p[n:], seg.data[st.off-seg.start:])
		n += m
		st.off += int64(m)
	}
	f.putStream(st)
	return n, nil
}

// fetchSegment starts fetching [start, start+segmentSize), retrying from
// where a dropped connection stopped.
func (f *File) fetchSegment(start int64) *segment {
	seg := &segment{start: start, done: make(chan struct{})}
	go func() {
		defer close(seg.done)
		end := min(start+segmentSize, f.src.size)
		buf := make([]byte, end-start)
		got := 0
		seg.err = f.retry(func(progress func()) error {
			resp, err := f.get(start+int64(got), end-1)
			if err != nil {
				return err
			}
			defer resp.Body.Close()
			m, err := io.ReadFull(&counted{resp.Body, f, progress}, buf[got:])
			got += m
			return err
		})
		if seg.err == nil {
			if f.src.decrypt != nil {
				f.src.decrypt(buf, start)
			}
			seg.data = buf
		}
	}()
	return seg
}

// counted counts bytes read and notes progress for the retry clock.
type counted struct {
	r        io.Reader
	f        *File
	progress func()
}

func (c *counted) Read(p []byte) (int, error) {
	n, err := c.r.Read(p)
	if n > 0 {
		c.f.received.Add(int64(n))
		c.progress()
	}
	return n, err
}

// statusError is an unexpected HTTP status.
type statusError struct {
	code int
	url  string
}

func (e *statusError) Error() string {
	return fmt.Sprintf("The download server answered %d %s", e.code, http.StatusText(e.code))
}

// permanent wraps errors that retrying cannot fix.
type permanent struct{ error }

func (p permanent) Unwrap() error { return p.error }

// get requests [start, end] (end -1: to the end of the file) from the URL in
// use and checks that the server sent exactly that range.
func (f *File) get(start, end int64) (*http.Response, error) {
	f.mu.Lock()
	u := f.src.urls[f.current]
	f.mu.Unlock()
	resp, err := rangeRequest(f.ctx, f.client, u, start, end)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusPartialContent {
		resp.Body.Close()
		if resp.StatusCode == http.StatusOK {
			return nil, permanent{fmt.Errorf("The download server sent the whole file instead of the requested range (bytes %d-), so Bunker cannot read the archive from it.", start)}
		}
		return nil, &statusError{resp.StatusCode, u}
	}
	got, _, total, ok := contentRange(resp.Header.Get("Content-Range"))
	if !ok || got != start || (total >= 0 && total != f.src.size) {
		resp.Body.Close()
		return nil, permanent{fmt.Errorf("The download server sent a different range than requested (%q for bytes %d-); the file may have changed.", resp.Header.Get("Content-Range"), start)}
	}
	return resp, nil
}

func rangeRequest(ctx context.Context, client *http.Client, u string, start, end int64) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return nil, permanent{err}
	}
	if end >= 0 {
		req.Header.Set("Range", fmt.Sprintf("bytes=%d-%d", start, end))
	} else {
		req.Header.Set("Range", fmt.Sprintf("bytes=%d-", start))
	}
	// Compressed transfer would make the byte positions meaningless.
	req.Header.Set("Accept-Encoding", "identity")
	req.Header.Set("User-Agent", "Bunker")
	return client.Do(req)
}

// contentRange parses "bytes a-b/total" (total -1 for "*").
func contentRange(h string) (start, end, total int64, ok bool) {
	spec, found := strings.CutPrefix(strings.TrimSpace(h), "bytes ")
	if !found {
		return 0, 0, 0, false
	}
	r, t, found := strings.Cut(spec, "/")
	if !found {
		return 0, 0, 0, false
	}
	a, b, found := strings.Cut(r, "-")
	if !found {
		return 0, 0, 0, false
	}
	var e1, e2 error
	start, e1 = strconv.ParseInt(a, 10, 64)
	end, e2 = strconv.ParseInt(b, 10, 64)
	if e1 != nil || e2 != nil {
		return 0, 0, 0, false
	}
	total = -1
	if t != "*" {
		if total, e1 = strconv.ParseInt(t, 10, 64); e1 != nil {
			return 0, 0, 0, false
		}
	}
	return start, end, total, true
}

// retry runs attempt until it succeeds, a permanent error, cancellation, or
// retryGiveUp without progress. attempt calls progress whenever data arrives.
func (f *File) retry(attempt func(progress func()) error) error {
	wait := retryFirst
	last := time.Now()
	progress := func() { last = time.Now(); wait = retryFirst }
	for {
		err := attempt(progress)
		if err == nil {
			return nil
		}
		if f.ctx.Err() != nil {
			return f.ctx.Err()
		}
		var perm permanent
		if errors.As(err, &perm) {
			return perm.error
		}
		var status *statusError
		if errors.As(err, &status) {
			if f.src.explain != nil {
				if friendly := f.src.explain(status.code); friendly != nil {
					return friendly
				}
			}
			switch {
			case status.code >= 500 || status.code == http.StatusRequestTimeout || status.code == http.StatusTooManyRequests:
				f.nextURL(status.url)
			case f.src.refresh != nil && (status.code == http.StatusForbidden || status.code == http.StatusNotFound || status.code == http.StatusGone):
				fresh, rerr := f.src.refresh(f.ctx)
				if rerr != nil {
					return rerr
				}
				f.mu.Lock()
				f.src.urls[f.current] = fresh
				f.mu.Unlock()
			default:
				return status
			}
		} else if !errors.Is(err, io.ErrUnexpectedEOF) && !errors.Is(err, io.EOF) {
			// A network error (connections drop in many ways): try the next mirror.
			f.nextURL("")
		}
		if time.Since(last) > retryGiveUp {
			return fmt.Errorf("The download stopped and did not resume for %s: %w", retryGiveUp, err)
		}
		select {
		case <-f.ctx.Done():
			return f.ctx.Err()
		case <-time.After(wait):
		}
		wait = min(wait*2, retryMax)
	}
}

// nextURL moves to the next mirror after failed, if failed is still in use.
func (f *File) nextURL(failed string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if len(f.src.urls) < 2 || (failed != "" && f.src.urls[f.current] != failed) {
		return
	}
	f.current = (f.current + 1) % len(f.src.urls)
}

// probe asks u for its first byte and returns the file's size, the final
// URL after redirects, and the response for callers that inspect it.
func probe(ctx context.Context, client *http.Client, u string) (size int64, final string, err error) {
	resp, err := rangeRequest(ctx, client, u, 0, 0)
	if err != nil {
		return 0, "", err
	}
	defer resp.Body.Close()
	switch resp.StatusCode {
	case http.StatusPartialContent:
	case http.StatusOK:
		return 0, "", ErrNoRanges
	default:
		return 0, "", &statusError{resp.StatusCode, u}
	}
	_, _, total, ok := contentRange(resp.Header.Get("Content-Range"))
	if !ok || total <= 0 {
		return 0, "", ErrNoRanges
	}
	return total, resp.Request.URL.String(), nil
}

// generic is a plain link to a server that accepts ranges.
func generic(ctx context.Context, client *http.Client, u *url.URL) (source, error) {
	size, final, err := probe(ctx, client, u.String())
	if err != nil {
		return source{}, err
	}
	name := path.Base(u.Path)
	if unescaped, err := url.PathUnescape(name); err == nil {
		name = unescaped
	}
	return source{
		urls: []string{final},
		size: size,
		id:   fmt.Sprintf("http %s%s %d", u.Host, u.Path, size),
		name: name,
		host: "http",
	}, nil
}
