package remotefile

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"math/rand"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// rangeServer serves blob and honours "Range: bytes=a-" and "bytes=a-b".
type rangeServer struct {
	blob     []byte
	requests atomic.Int64
	// dropAfter, when > 0, cuts the next body after that many bytes once.
	dropAfter atomic.Int64
	// ignoreRanges makes every request after the first answer 200 with the whole blob.
	ignoreRanges atomic.Bool
	noRanges     bool
}

func (s *rangeServer) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	n := s.requests.Add(1)
	h := r.Header.Get("Range")
	if s.noRanges || h == "" || (s.ignoreRanges.Load() && n > 1) {
		w.Header().Set("Content-Length", strconv.Itoa(len(s.blob)))
		w.WriteHeader(http.StatusOK)
		w.Write(s.blob)
		return
	}
	start, end := parseRange(h, int64(len(s.blob)))
	w.Header().Set("Content-Range", fmt.Sprintf("bytes %d-%d/%d", start, end, len(s.blob)))
	w.Header().Set("Content-Length", strconv.FormatInt(end-start+1, 10))
	w.WriteHeader(http.StatusPartialContent)
	body := s.blob[start : end+1]
	if cut := s.dropAfter.Swap(0); cut > 0 && cut < int64(len(body)) {
		w.Write(body[:cut])
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}
		panic(http.ErrAbortHandler)
	}
	w.Write(body)
}

func parseRange(h string, size int64) (int64, int64) {
	spec := strings.TrimPrefix(h, "bytes=")
	a, b, _ := strings.Cut(spec, "-")
	start, _ := strconv.ParseInt(a, 10, 64)
	end := size - 1
	if b != "" {
		end, _ = strconv.ParseInt(b, 10, 64)
	}
	if end >= size {
		end = size - 1
	}
	return start, end
}

func blob(n int) []byte {
	b := make([]byte, n)
	rand.New(rand.NewSource(1)).Read(b)
	return b
}

func fastRetries(t *testing.T) {
	oldFirst, oldMax, oldGive := retryFirst, retryMax, retryGiveUp
	retryFirst, retryMax, retryGiveUp = 5*time.Millisecond, 20*time.Millisecond, 2*time.Second
	t.Cleanup(func() { retryFirst, retryMax, retryGiveUp = oldFirst, oldMax, oldGive })
}

func open(t *testing.T, s *rangeServer) *File {
	t.Helper()
	srv := httptest.NewServer(s)
	t.Cleanup(srv.Close)
	f, err := Open(context.Background(), srv.URL+"/dump.7z", srv.Client())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { f.Close() })
	return f
}

func TestReadAtMatches(t *testing.T) {
	s := &rangeServer{blob: blob(5 << 20)}
	f := open(t, s)
	if f.Size() != int64(len(s.blob)) || f.Name() != "dump.7z" || f.Host() != "http" {
		t.Fatalf("size %d name %q host %q", f.Size(), f.Name(), f.Host())
	}
	var wg sync.WaitGroup
	errs := make(chan error, 8)
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func(seed int64) {
			defer wg.Done()
			r := rand.New(rand.NewSource(seed))
			for i := 0; i < 25; i++ {
				n := 1 + r.Intn(200<<10)
				off := r.Int63n(int64(len(s.blob) - n))
				p := make([]byte, n)
				if _, err := f.ReadAt(p, off); err != nil {
					errs <- err
					return
				}
				if !bytes.Equal(p, s.blob[off:off+int64(n)]) {
					errs <- fmt.Errorf("mismatch at %d+%d", off, n)
					return
				}
			}
		}(int64(g))
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		t.Fatal(err)
	}
}

func TestReadAtEOF(t *testing.T) {
	s := &rangeServer{blob: blob(1000)}
	f := open(t, s)
	p := make([]byte, 100)
	n, err := f.ReadAt(p, 950)
	if n != 50 || err == nil {
		t.Fatalf("got %d, %v; want 50 and EOF", n, err)
	}
}

func TestSequentialReuse(t *testing.T) {
	s := &rangeServer{blob: blob(5 << 20)}
	f := open(t, s)
	before := s.requests.Load()
	p := make([]byte, 64<<10)
	for i := int64(0); i < 64; i++ {
		off := (1 << 20) + i*int64(len(p))
		if _, err := f.ReadAt(p, off); err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(p, s.blob[off:off+int64(len(p))]) {
			t.Fatalf("mismatch at %d", off)
		}
	}
	// One cached chunk, then the stream's 4 MB pieces with read-ahead.
	if got := s.requests.Load() - before; got > 1+4/(segmentSize>>20)+aheadSegments {
		t.Fatalf("64 sequential reads used %d requests", got)
	}
	if f.Received() < 4<<20 {
		t.Fatalf("Received %d, want at least 4 MB", f.Received())
	}
}

func TestReadAtRetriesDroppedConnection(t *testing.T) {
	fastRetries(t)
	s := &rangeServer{blob: blob(3 << 20)}
	f := open(t, s)
	s.dropAfter.Store(100 << 10)
	p := make([]byte, 2<<20)
	if _, err := f.ReadAt(p, 500<<10); err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(p, s.blob[500<<10:(500<<10)+len(p)]) {
		t.Fatal("data differs after the retry")
	}
}

func TestReadAtRejectsFullResponse(t *testing.T) {
	fastRetries(t)
	s := &rangeServer{blob: blob(3 << 20)}
	f := open(t, s)
	s.ignoreRanges.Store(true)
	p := make([]byte, 200<<10)
	_, err := f.ReadAt(p, 1<<20)
	if err == nil || !strings.Contains(err.Error(), "range") {
		t.Fatalf("err = %v, want a range error", err)
	}
}

func TestOpenNoRanges(t *testing.T) {
	srv := httptest.NewServer(&rangeServer{blob: blob(1000), noRanges: true})
	defer srv.Close()
	_, err := Open(context.Background(), srv.URL+"/x.7z", srv.Client())
	if !errors.Is(err, ErrNoRanges) {
		t.Fatalf("err = %v, want ErrNoRanges", err)
	}
}

func TestCancel(t *testing.T) {
	fastRetries(t)
	retryFirst, retryMax = time.Second, time.Second
	var calls atomic.Int64
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if calls.Add(1) == 1 {
			w.Header().Set("Content-Range", "bytes 0-0/1000000")
			w.WriteHeader(http.StatusPartialContent)
			w.Write([]byte{0})
			return
		}
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer srv.Close()
	ctx, cancel := context.WithCancel(context.Background())
	f, err := Open(ctx, srv.URL+"/x.7z", srv.Client())
	if err != nil {
		t.Fatal(err)
	}
	done := make(chan error)
	go func() {
		_, err := f.ReadAt(make([]byte, 10), 5000)
		done <- err
	}()
	time.Sleep(50 * time.Millisecond)
	cancel()
	select {
	case err := <-done:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("err = %v, want context.Canceled", err)
		}
	case <-time.After(500 * time.Millisecond):
		t.Fatal("ReadAt did not return after cancel")
	}
}

func TestIsLink(t *testing.T) {
	for s, want := range map[string]bool{"https://x/y.7z": true, "http://x": true, "HTTPS://X": true, "C:\\dump.7z": false, "/tmp/a.7z": false, "": false} {
		if IsLink(s) != want {
			t.Errorf("IsLink(%q) = %v", s, !want)
		}
	}
}

// A stream fetches its next pieces at the same time: archive.org sends each
// connection about 1 MB/s, and more connections are faster.
func TestReadAheadOverlaps(t *testing.T) {
	s := &rangeServer{blob: blob(40 << 20)}
	var inFlight, most atomic.Int64
	slow := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := inFlight.Add(1)
		defer inFlight.Add(-1)
		for {
			m := most.Load()
			if n <= m || most.CompareAndSwap(m, n) {
				break
			}
		}
		if r.Header.Get("Range") != "bytes=0-0" {
			time.Sleep(30 * time.Millisecond)
		}
		s.ServeHTTP(w, r)
	})
	srv := httptest.NewServer(slow)
	defer srv.Close()
	f, err := Open(context.Background(), srv.URL+"/d.7z", srv.Client())
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	p := make([]byte, 256<<10)
	for off := int64(0); off < 30<<20; off += int64(len(p)) {
		if _, err := f.ReadAt(p, off); err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(p, s.blob[off:off+int64(len(p))]) {
			t.Fatalf("mismatch at %d", off)
		}
	}
	if most.Load() < 3 {
		t.Fatalf("at most %d requests at once; read-ahead should overlap them", most.Load())
	}
}
