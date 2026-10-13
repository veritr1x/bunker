package interceptor

import (
	"context"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func TestRecover(t *testing.T) {
	info := &grpc.UnaryServerInfo{FullMethod: "/apb.api.test.TestService/Panic"}
	resp, err := Recover(context.Background(), nil, info, func(context.Context, any) (any, error) {
		var m map[string]int
		m["x"] = 1 // panics
		return "unreachable", nil
	})
	if resp != nil || status.Code(err) != codes.Internal {
		t.Fatalf("panic: resp=%v err=%v", resp, err)
	}
	resp, err = Recover(context.Background(), nil, info, func(context.Context, any) (any, error) { return "ok", nil })
	if resp != "ok" || err != nil {
		t.Fatalf("no panic: resp=%v err=%v", resp, err)
	}
}
