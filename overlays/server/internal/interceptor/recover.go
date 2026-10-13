package interceptor

import (
	"context"
	"log"
	"runtime/debug"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Recover turns a panic in a handler (or in the interceptors after it) into an
// Internal error for that one request, with the stack in the log. gRPC runs
// each request on its own goroutine without recovering, so a panic would
// otherwise take the whole server down; on the phone that is the game too.
// It goes first in the chain so it covers every other interceptor.
func Recover(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (resp any, err error) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("<<< %s PANIC: %v\n%s", info.FullMethod, r, debug.Stack())
			resp, err = nil, status.Errorf(codes.Internal, "internal error in %s", info.FullMethod)
		}
	}()
	return handler(ctx, req)
}
