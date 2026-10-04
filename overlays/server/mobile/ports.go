package mobile

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"sync/atomic"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health/grpc_health_v1"
)

// The game reaches the server on fixed loopback ports, written into the game
// when it is built: 8003 (game), 8080 (assets) and 3000 (accounts). A build
// may move all three by the same offset (scripts/build.py --port-offset), for
// phones where another app already uses one of them. The launcher passes that
// offset here before starting the server.
const serviceName = "lunar-tear"

var (
	portOffset    atomic.Int64
	portOffsetSet atomic.Bool
)

// SetPortOffset sets the build's port offset. Returns "" or an error.
func SetPortOffset(offset int) string {
	if offset < 0 || 8080+offset > 65535 {
		return fmt.Sprintf("Port offset %d is out of range", offset)
	}
	portOffset.Store(int64(offset))
	portOffsetSet.Store(true)
	return ""
}

func offset() int {
	if portOffsetSet.Load() {
		return int(portOffset.Load())
	}
	// Automated tests on a computer where the ports are in use.
	var o int
	fmt.Sscan(os.Getenv("LUNAR_PORT_OFFSET"), &o)
	return o
}

// local returns the loopback address for one of the game's ports.
func local(port int) string { return fmt.Sprintf("127.0.0.1:%d", port+offset()) }

// Ports reports the ports in use, as {"game":8003,"assets":8080,"accounts":3000}.
func Ports() string {
	b, _ := json.Marshal(map[string]int{"game": 8003 + offset(), "assets": 8080 + offset(), "accounts": 3000 + offset()})
	return string(b)
}

// listen opens one of the server's ports, explaining the usual failure.
func listen(addr string) (net.Listener, error) {
	l, e := net.Listen("tcp", addr)
	if errors.Is(e, syscall.EADDRINUSE) {
		_, port, _ := net.SplitHostPort(addr)
		return nil, fmt.Errorf("Port %s is already used by another app on this device, so the game cannot reach its server. "+
			"Close or uninstall that app, or build with a different --port-offset", port)
	}
	if e != nil {
		return nil, fmt.Errorf("cannot open %s: %w", addr, e)
	}
	return l, nil
}

type check struct {
	Name   string `json:"name"`
	Port   int    `json:"port"`
	OK     bool   `json:"ok"`
	Detail string `json:"detail,omitempty"`
}

// SelfTest connects to each port the way the game does and confirms that
// this server, not another app, answers. Returns
// {"ok":true,"checks":[{"name":"game","port":8003,"ok":true},...]}.
func SelfTest() string {
	checks := []check{checkGame(), checkHTTP("assets", 8080), checkHTTP("accounts", 3000)}
	ok := true
	for _, c := range checks {
		ok = ok && c.OK
	}
	b, _ := json.Marshal(map[string]any{"ok": ok, "checks": checks})
	return string(b)
}

func checkGame() check {
	c := check{Name: "game", Port: 8003 + offset()}
	conn, e := grpc.NewClient(local(8003), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if e != nil {
		c.Detail = e.Error()
		return c
	}
	defer conn.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	r, e := grpc_health_v1.NewHealthClient(conn).Check(ctx, &grpc_health_v1.HealthCheckRequest{})
	switch {
	case e != nil:
		c.Detail = "no answer from the game service: " + e.Error()
	case r.Status != grpc_health_v1.HealthCheckResponse_SERVING:
		c.Detail = "game service is " + r.Status.String()
	default:
		c.OK = true
	}
	return c
}

func checkHTTP(name string, port int) check {
	c := check{Name: name, Port: port + offset()}
	client := &http.Client{Timeout: 3 * time.Second}
	resp, e := client.Get("http://" + local(port) + "/companion/health")
	if e != nil {
		c.Detail = "no answer: " + e.Error()
		return c
	}
	defer resp.Body.Close()
	var body struct{ Status, Service string }
	json.NewDecoder(resp.Body).Decode(&body)
	if body.Service != serviceName || body.Status != "ok" {
		c.Detail = fmt.Sprintf("another program answers on port %d (HTTP %d)", c.Port, resp.StatusCode)
		return c
	}
	c.OK = true
	return c
}

// healthHandler identifies this server, so a check cannot be fooled by another app.
func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"status":"ok","service":%q}`, serviceName)
}
