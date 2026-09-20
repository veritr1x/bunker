package mobile

import (
	"context"
	"encoding/json"
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
	for _, addr := range []string{"127.0.0.1:8003", "127.0.0.1:8080", "127.0.0.1:3000"} {
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
	occupied, e := net.Listen("tcp", "127.0.0.1:8080")
	if e != nil {
		t.Fatal(e)
	}
	if e = Start(data, root); e == nil {
		t.Fatal("accepted occupied port")
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
			client := &http.Client{Timeout: 5 * time.Second}
			req, _ := http.NewRequest("GET", "http://127.0.0.1:8080/unso-1-assetbundle/abc123", nil)
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
			for _, url := range []string{"http://127.0.0.1:8080/companion/health", "http://127.0.0.1:3000/v18.0/dialog/oauth"} {
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
			conn, e := grpc.NewClient("127.0.0.1:8003", grpc.WithTransportCredentials(insecure.NewCredentials()))
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
			if config.Api.Hostname != "127.0.0.1" || config.Api.Port != 8003 || config.Octo.Url != "http://127.0.0.1:8080" {
				t.Fatalf("external endpoint: %v", config)
			}
		}()
	}
	for _, addr := range []string{"127.0.0.1:8003", "127.0.0.1:8080", "127.0.0.1:3000"} {
		l, e := net.Listen("tcp", addr)
		if e != nil {
			t.Fatal(e)
		}
		l.Close()
	}
}
