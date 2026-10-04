// Package mobile embeds the upstream services in a single Android process.
package mobile

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"lunar-tear/server/internal/auth"
	"lunar-tear/server/internal/database"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/interceptor"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/service"
	"lunar-tear/server/internal/store/sqlite"
	"lunar-tear/server/migrations"

	"golang.org/x/net/http2"
	"golang.org/x/net/http2/h2c"
	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	"google.golang.org/grpc/health/grpc_health_v1"
)

const MasterName = "20240404193219.bin.e"

var lifecycle sync.Mutex
var active *instance
var statusMu sync.Mutex
var phase = "stopped"
var lastError string
var logs logBuffer

type logBuffer struct {
	sync.Mutex
	data []byte
}

func (b *logBuffer) Write(p []byte) (int, error) {
	b.Lock()
	defer b.Unlock()
	b.data = append(b.data, p...)
	if len(b.data) > 32768 {
		b.data = append([]byte(nil), b.data[len(b.data)-32768:]...)
	}
	return len(p), nil
}
func init() { log.SetOutput(io.MultiWriter(os.Stderr, &logs)) }

func setStatus(p, e string) { statusMu.Lock(); phase, lastError = p, e; statusMu.Unlock() }
func Status() string {
	statusMu.Lock()
	p, e := phase, lastError
	statusMu.Unlock()
	logs.Lock()
	l := string(logs.data)
	logs.Unlock()
	b, _ := json.Marshal(map[string]string{"state": p, "error": e, "logs": l})
	return string(b)
}

// Validate checks the minimum structure, not the completeness of the asset catalog.
func Validate(root string) error {
	for _, p := range []string{filepath.Join("assets", "release", MasterName)} {
		s, e := os.Stat(filepath.Join(root, p))
		if e != nil || !s.Mode().IsRegular() || s.Size() == 0 {
			return fmt.Errorf("import master data (%s) before starting", MasterName)
		}
	}
	for _, p := range []string{"assets/revisions/0/android/list.bin", "assets/revisions/0/list.bin"} {
		if s, e := os.Stat(filepath.Join(root, p)); e == nil && s.Mode().IsRegular() && s.Size() > 0 {
			return nil
		}
	}
	return errors.New("import the extracted assets folder; Android revisions/0/android/list.bin is missing")
}

type instance struct {
	grpc      *grpc.Server
	http      []*http.Server
	listeners []net.Listener
	dbs       []*sql.DB
}

func (s *instance) close() {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if s.grpc != nil {
		done := make(chan struct{})
		go func() { s.grpc.GracefulStop(); close(done) }()
		select {
		case <-done:
		case <-ctx.Done():
			s.grpc.Stop()
			<-done
		}
	}
	for _, h := range s.http {
		if h.Shutdown(ctx) != nil {
			h.Close()
		}
	}
	for _, l := range s.listeners {
		l.Close()
	}
	for _, db := range s.dbs {
		database.Checkpoint(db)
		db.Close()
	}
}

// Start blocks until all three listeners and data stores are ready. All endpoints
// are loopback-only; no router, internet connection, or account is required.
func Start(dataRoot, assetRoot string) (err error) {
	lifecycle.Lock()
	defer lifecycle.Unlock()
	if active != nil {
		return nil
	}
	setStatus("starting", "")
	s := &instance{}
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("server initialization failed: %v", r)
		}
		if err != nil {
			s.close()
			setStatus("error", err.Error())
			log.Printf("Start failed: %v", err)
		}
	}()
	if err = Validate(assetRoot); err != nil {
		return err
	}
	// Reserve all ports before changing databases or loading catalogs.
	for _, addr := range []string{local(8003), local(8080), local(3000)} {
		l, e := listen(addr)
		if e != nil {
			return e
		}
		s.listeners = append(s.listeners, l)
	}
	if err = os.MkdirAll(dataRoot, 0700); err != nil {
		return err
	}
	db, e := database.Open(filepath.Join(dataRoot, "game.db"))
	if e != nil {
		return e
	}
	s.dbs = append(s.dbs, db)
	if e = migrations.Up(context.Background(), db); e != nil {
		return fmt.Errorf("prepare save database: %w", e)
	}
	holder, e := runtime.NewHolder(filepath.Join(assetRoot, "assets", "release", MasterName))
	if e != nil {
		return fmt.Errorf("load master data: %w", e)
	}
	authDB, e := database.Open(filepath.Join(dataRoot, "auth.db"))
	if e != nil {
		return e
	}
	s.dbs = append(s.dbs, authDB)
	authStore, e := auth.NewAuthStore(authDB)
	if e != nil {
		return e
	}
	secret, e := loadSecret(filepath.Join(dataRoot, "auth.key"))
	if e != nil {
		return e
	}
	h := NewHandlers(authStore, auth.NewTokenService(secret), false)
	mux := http.NewServeMux()
	mux.HandleFunc("/", h.HandleOAuth)
	mux.HandleFunc("/me", h.HandleMe)
	mux.HandleFunc("/check-username", h.HandleCheckUsername)
	mux.HandleFunc("/companion/health", healthHandler)
	authHTTP := &http.Server{Handler: mux, ReadHeaderTimeout: 10 * time.Second}
	cdnURL := "http://" + local(8080)
	prefix := cdnURL + "/"
	service.ResetOctoCaches()
	cdn := service.NewOctoHTTPServer(prefix+strings.Repeat("r", 43-len(prefix)), assetRoot)
	cdnMux := http.NewServeMux()
	cdnMux.HandleFunc("/companion/health", healthHandler)
	cdnMux.Handle("/", cdn.Handler())
	cdnHTTP := &http.Server{Handler: h2c.NewHandler(cdnMux, &http2.Server{}), ReadHeaderTimeout: 10 * time.Second}
	s.http = []*http.Server{cdnHTTP, authHTTP}
	store := sqlite.New(db, gametime.Now)
	s.grpc = grpc.NewServer(grpc.ChainUnaryInterceptor(interceptor.Platform, interceptor.Logging, interceptor.NewDiffInterceptor(store, store), interceptor.TimeSync), grpc.UnknownServiceHandler(interceptor.UnknownService))
	registerServices(s.grpc, local(8003), cdnURL, "http://"+local(3000), filepath.Join(assetRoot, "assets", "release", MasterName), store, holder, false)
	healthServer := health.NewServer()
	healthServer.SetServingStatus("", grpc_health_v1.HealthCheckResponse_SERVING)
	grpc_health_v1.RegisterHealthServer(s.grpc, healthServer)
	active = s
	serveError := func(e error) {
		if e != nil && !errors.Is(e, http.ErrServerClosed) && !errors.Is(e, grpc.ErrServerStopped) && !errors.Is(e, net.ErrClosed) {
			log.Printf("Listener failed: %v", e)
			lifecycle.Lock()
			defer lifecycle.Unlock()
			if active == s {
				active = nil
				s.close()
				setStatus("error", e.Error())
			}
		}
	}
	go func() { serveError(s.grpc.Serve(s.listeners[0])) }()
	go func() { serveError(cdnHTTP.Serve(s.listeners[1])) }()
	go func() { serveError(authHTTP.Serve(s.listeners[2])) }()
	setStatus("running", "")
	log.Printf("Local server ready: game %d, assets %d, accounts %d", 8003+offset(), 8080+offset(), 3000+offset())
	return nil
}

func Stop() {
	lifecycle.Lock()
	defer lifecycle.Unlock()
	if active != nil {
		setStatus("stopping", "")
		s := active
		active = nil
		s.close()
	}
	setStatus("stopped", "")
	log.Print("Server stopped; saves flushed")
}

func loadSecret(path string) ([]byte, error) {
	b, e := os.ReadFile(path)
	if e == nil {
		decoded, e := hex.DecodeString(strings.TrimSpace(string(b)))
		if e != nil || len(decoded) != 32 {
			return nil, errors.New("invalid saved auth key")
		}
		return decoded, nil
	}
	if !os.IsNotExist(e) {
		return nil, e
	}
	secret := make([]byte, 32)
	if _, e = rand.Read(secret); e != nil {
		return nil, e
	}
	if e = os.WriteFile(path, []byte(hex.EncodeToString(secret)), 0600); e != nil {
		return nil, e
	}
	return secret, nil
}

// CheckDatabase is a real SQLite/migration smoke check, also callable on-device.
func CheckDatabase(root string) string {
	lifecycle.Lock()
	defer lifecycle.Unlock()
	p := filepath.Join(root, "diagnostic.db")
	db, e := database.Open(p)
	if e != nil {
		return e.Error()
	}
	defer func() {
		database.Checkpoint(db)
		db.Close()
		os.Remove(p)
		os.Remove(p + "-wal")
		os.Remove(p + "-shm")
	}()
	if e = migrations.Up(context.Background(), db); e != nil {
		return e.Error()
	}
	var result string
	if e = db.QueryRow("PRAGMA integrity_check").Scan(&result); e != nil {
		return e.Error()
	}
	if result != "ok" {
		return result
	}
	return ""
}

// PrepareBackup recovers and checkpoints WAL files left by an Android process
// kill before Java copies the databases. The server must be stopped.
func PrepareBackup(root string) string {
	lifecycle.Lock()
	defer lifecycle.Unlock()
	if active != nil {
		return "Stop the server before exporting saves"
	}
	for _, name := range []string{"game.db", "auth.db"} {
		path := filepath.Join(root, name)
		if _, e := os.Stat(path); os.IsNotExist(e) {
			continue
		}
		db, e := database.Open(path)
		if e != nil {
			return e.Error()
		}
		var busy, pages, copied int
		e = db.QueryRow("PRAGMA wal_checkpoint(TRUNCATE)").Scan(&busy, &pages, &copied)
		db.Close()
		if e != nil {
			return e.Error()
		}
		if busy != 0 {
			return "Save database is busy; try exporting again after stopping the game"
		}
	}
	return ""
}
