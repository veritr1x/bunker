package mobile

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/encoding/protowire"
	"google.golang.org/protobuf/types/known/emptypb"
	pb "lunar-tear/server/gen/proto"
)

func TestMissingAssetsDoesNotOpenPorts(t *testing.T) {
	Stop()
	if e := Start(t.TempDir(), t.TempDir()); e == nil {
		t.Fatal("start accepted missing assets")
	}
	var s map[string]string
	json.Unmarshal([]byte(Status()), &s)
	if s["state"] != "error" {
		t.Fatalf("status %v", s)
	}
	for _, addr := range []string{local(8003), local(8080), local(3000)} {
		l, e := net.Listen("tcp", addr)
		if e != nil {
			t.Fatal(e)
		}
		l.Close()
	}
}

func TestSQLiteMigrationsAndKeyPersistence(t *testing.T) {
	root := t.TempDir()
	if e := CheckDatabase(root); e != "" {
		t.Fatal(e)
	}
	a, e := loadSecret(filepath.Join(root, "key"))
	if e != nil {
		t.Fatal(e)
	}
	b, e := loadSecret(filepath.Join(root, "key"))
	if e != nil {
		t.Fatal(e)
	}
	if string(a) != string(b) {
		t.Fatal("auth key changed across restart")
	}
	os.WriteFile(filepath.Join(root, "key"), []byte("broken"), 0600)
	if _, e = loadSecret(filepath.Join(root, "key")); e == nil {
		t.Fatal("corrupt auth key silently replaced")
	}
}

// Uses the user's master data only when explicitly supplied. The placeholder
// index exercises startup and protocols; it does NOT prove asset completeness.
func TestLocalServicesWithRealMasterData(t *testing.T) {
	source := os.Getenv("LUNAR_TEST_MASTER")
	if source == "" {
		t.Skip("set LUNAR_TEST_MASTER for real master-data integration test")
	}
	root := t.TempDir()
	data := t.TempDir()
	os.MkdirAll(filepath.Join(root, "assets/release"), 0700)
	os.MkdirAll(filepath.Join(root, "assets/revisions/0/android"), 0700)
	b, e := os.ReadFile(source)
	if e != nil {
		t.Fatal(e)
	}
	os.WriteFile(filepath.Join(root, "assets/release", MasterName), b, 0600)
	os.WriteFile(filepath.Join(root, "assets/revisions/0/android/list.bin"), []byte{0x08, 0x01}, 0600)
	// Failed starts must roll back any earlier port reservations.
	occupied, e := net.Listen("tcp", local(8080))
	if e != nil {
		t.Fatal(e)
	}
	if e = Start(data, root); e == nil || !strings.Contains(e.Error(), "already used by another app") {
		t.Fatalf("occupied port: got %v", e)
	}
	occupied.Close()
	for iteration := 0; iteration < 2; iteration++ {
		// Importing a replacement catalog while the Android process stays alive
		// must invalidate the old object-ID mapping on the next server start.
		name := []string{"first", "replacement"}[iteration]
		entry := protowire.AppendTag(nil, 3, protowire.BytesType)
		entry = protowire.AppendString(entry, name)
		entry = protowire.AppendTag(entry, 11, protowire.BytesType)
		entry = protowire.AppendString(entry, "abc123")
		catalog := protowire.AppendTag(nil, 2, protowire.BytesType)
		catalog = protowire.AppendBytes(catalog, entry)
		os.WriteFile(filepath.Join(root, "assets/revisions/0/android/list.bin"), catalog, 0600)
		os.MkdirAll(filepath.Join(root, "assets/revisions/0/android/assetbundle"), 0700)
		os.WriteFile(filepath.Join(root, "assets/revisions/0/android/assetbundle", name+".assetbundle"), []byte(strings.Repeat(name, 100)), 0600)
		if e = Start(data, root); e != nil {
			t.Fatal(e)
		}
		func() {
			defer Stop()
			var test struct{ OK bool }
			if report := SelfTest(); json.Unmarshal([]byte(report), &test) != nil || !test.OK {
				t.Fatalf("self-test failed on a running server: %s", report)
			}
			client := &http.Client{Timeout: 5 * time.Second}
			req, _ := http.NewRequest("GET", "http://"+local(8080)+"/unso-1-assetbundle/abc123", nil)
			req.Header.Set("User-Agent", "Android")
			asset, err := client.Do(req)
			if err != nil {
				t.Fatal(err)
			}
			body, err := io.ReadAll(asset.Body)
			asset.Body.Close()
			if err != nil || asset.StatusCode != 200 || string(body) != strings.Repeat(name, 100) {
				t.Fatalf("replacement asset not served: status=%d body=%q error=%v", asset.StatusCode, body, err)
			}
			for _, url := range []string{"http://" + local(8080) + "/companion/health", "http://" + local(3000) + "/v18.0/dialog/oauth"} {
				resp, e := client.Get(url)
				if e != nil {
					t.Fatal(e)
				}
				io.Copy(io.Discard, resp.Body)
				resp.Body.Close()
				if resp.StatusCode != 200 {
					t.Fatal(resp.Status)
				}
			}
			conn, e := grpc.NewClient(local(8003), grpc.WithTransportCredentials(insecure.NewCredentials()))
			if e != nil {
				t.Fatal(e)
			}
			defer conn.Close()
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			version, err := pb.NewDataServiceClient(conn).GetLatestMasterDataVersion(ctx, &emptypb.Empty{})
			if err != nil || !strings.HasPrefix(version.GetLatestMasterDataVersion(), "20240404193219_") {
				t.Fatalf("master version did not use imported file: %v, %v", version, err)
			}
			config, e := pb.NewConfigServiceClient(conn).GetReviewServerConfig(ctx, &emptypb.Empty{})
			if e != nil {
				t.Fatal(e)
			}
			if fmt.Sprintf("%s:%d", config.Api.Hostname, config.Api.Port) != local(8003) || config.Octo.Url != "http://"+local(8080) {
				t.Fatalf("external endpoint: %v", config)
			}
		}()
	}
	for _, addr := range []string{local(8003), local(8080), local(3000)} {
		l, e := net.Listen("tcp", addr)
		if e != nil {
			t.Fatal(e)
		}
		l.Close()
	}
}

// Another program on one of the ports must not pass for this server.
func TestSelfTestRejectsAnotherProgram(t *testing.T) {
	Stop()
	defer portOffsetSet.Store(false)
	if e := SetPortOffset(-1); e == "" {
		t.Fatal("accepted a negative offset")
	}
	SetPortOffset(offset() + 1000)
	var ports map[string]int
	json.Unmarshal([]byte(Ports()), &ports)
	if ports["game"] != 8003+offset() || ports["assets"] != 8080+offset() || ports["accounts"] != 3000+offset() {
		t.Fatalf("ports %v", ports)
	}
	l, e := net.Listen("tcp", local(8080))
	if e != nil {
		t.Fatal(e)
	}
	impostor := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		io.WriteString(w, `{"status":"ok"}`)
	})}
	go impostor.Serve(l)
	defer impostor.Close()
	var report struct {
		OK     bool
		Checks []check
	}
	json.Unmarshal([]byte(SelfTest()), &report)
	if report.OK || len(report.Checks) != 3 {
		t.Fatalf("self-test passed without the server: %+v", report)
	}
	for _, c := range report.Checks {
		if c.OK {
			t.Fatalf("%s passed without the server", c.Name)
		}
		if c.Name == "assets" && !strings.Contains(c.Detail, "another program") {
			t.Fatalf("impostor not identified: %q", c.Detail)
		}
	}
}
