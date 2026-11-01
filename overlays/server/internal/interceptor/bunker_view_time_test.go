package interceptor

import (
	"context"
	"strings"
	"testing"
	"time"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/gametime"

	"google.golang.org/grpc"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/reflect/protoregistry"
	"google.golang.org/protobuf/types/known/timestamppb"
)

const week = int64(7 * 24 * 3600 * 1000)

func near(a, b int64) bool { return a-b < 1000 && b-a < 1000 }

// The time trailer is the game's clock: in the original-dates view it runs
// the calendar's offset behind.
func TestTrailerShowsTheViewClock(t *testing.T) {
	defer gametime.SetCalendar(nil)
	c := &gametime.Calendar{Loop: 1, LoopStart: gametime.Launch + 100*week}
	gametime.SetCalendar(c)
	if !near(viewNowMillis(), gametime.NowMillis()) {
		t.Fatal("moved with the setting off")
	}
	c.OriginalDates = true
	if !near(viewNowMillis(), gametime.NowMillis()-100*week) {
		t.Fatalf("view clock %d, now %d", viewNowMillis(), gametime.NowMillis())
	}
}

func gachaList(start, end int64) *pb.GetGachaListResponse {
	return &pb.GetGachaListResponse{Gacha: []*pb.Gacha{{
		GachaId:       1,
		StartDatetime: timestamppb.New(time.UnixMilli(start)),
		EndDatetime:   timestamppb.New(time.UnixMilli(end)),
	}}}
}

func runViewTimes(t *testing.T, resp proto.Message) proto.Message {
	t.Helper()
	out, err := ViewTimes(context.Background(), nil, &grpc.UnaryServerInfo{FullMethod: "/x"}, func(context.Context, any) (any, error) { return resp, nil })
	if err != nil {
		t.Fatal(err)
	}
	return out.(proto.Message)
}

// Response times (summon dates, gift expiry...) are in the view; "forever" stays.
func TestViewTimesMovesNestedTimestamps(t *testing.T) {
	defer gametime.SetCalendar(nil)
	gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: gametime.Launch + 100*week, OriginalDates: true})
	start := gametime.Launch + 110*week
	resp := gachaList(start, 253402300799000)
	got := runViewTimes(t, resp).(*pb.GetGachaListResponse).Gacha[0]
	if got.StartDatetime.AsTime().UnixMilli() != start-100*week || got.EndDatetime.AsTime().UnixMilli() != 253402300799000 {
		t.Fatalf("start %v end %v", got.StartDatetime.AsTime(), got.EndDatetime.AsTime())
	}
	if resp.Gacha[0].StartDatetime.AsTime().UnixMilli() != start {
		t.Fatal("the handler's message was changed (it may be shared)")
	}
}

func TestViewTimesOffsetZeroLeavesResponse(t *testing.T) {
	gametime.SetCalendar(nil)
	resp := gachaList(gametime.Launch+110*week, gametime.Launch+111*week)
	if got := runViewTimes(t, resp); got != proto.Message(resp) {
		t.Fatal("response replaced with the view off")
	}
}

// Every time the game is sent is a Timestamp (moved by ViewTimes) or a
// ...Datetime field of player data JSON (viewJSON): no message carries one as
// a plain number.
func TestNoDatetimeIntsInResponses(t *testing.T) {
	scanned := 0
	protoregistry.GlobalFiles.RangeFiles(func(fd protoreflect.FileDescriptor) bool {
		if !strings.HasPrefix(string(fd.Package()), "apb.") {
			return true
		}
		var walk func(protoreflect.MessageDescriptors)
		walk = func(ms protoreflect.MessageDescriptors) {
			for i := 0; i < ms.Len(); i++ {
				m := ms.Get(i)
				scanned++
				for j := 0; j < m.Fields().Len(); j++ {
					f := m.Fields().Get(j)
					name := strings.ToLower(string(f.Name()))
					if (f.Kind() == protoreflect.Int64Kind || f.Kind() == protoreflect.Int32Kind) && (strings.HasSuffix(name, "datetime") || strings.HasSuffix(name, "_at")) {
						t.Errorf("%s.%s is a time as a number", m.FullName(), f.Name())
					}
				}
				walk(m.Messages())
			}
		}
		walk(fd.Messages())
		return true
	})
	if scanned < 500 {
		t.Fatalf("only %d messages scanned", scanned)
	}
}
