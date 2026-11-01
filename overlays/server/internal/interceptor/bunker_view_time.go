package interceptor

import (
	"context"
	"time"

	"lunar-tear/server/internal/gametime"

	"google.golang.org/grpc"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// viewNowMillis is the clock the game is sent: in the original-dates view the
// calendar's offset behind (gametime.ViewOffset).
func viewNowMillis() int64 {
	return gametime.NowMillis() - gametime.ViewOffset()
}

const timestampName protoreflect.FullName = "google.protobuf.Timestamp"

// ViewTimes sends the game every Timestamp of a response in the original-dates
// view (gametime.ToView). It works on a copy: handlers may return messages
// they keep.
func ViewTimes(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
	resp, err := handler(ctx, req)
	msg, ok := resp.(proto.Message)
	if err != nil || !ok || gametime.ViewOffset() == 0 {
		return resp, err
	}
	out := proto.Clone(msg)
	viewMessage(out.ProtoReflect())
	return out, nil
}

func viewMessage(m protoreflect.Message) {
	if m.Descriptor().FullName() == timestampName {
		ts := m.Interface().(*timestamppb.Timestamp)
		ms := ts.AsTime().UnixMilli()
		if v := gametime.ToView(ms); v != ms {
			moved := timestamppb.New(time.UnixMilli(v))
			ts.Seconds, ts.Nanos = moved.Seconds, moved.Nanos
		}
		return
	}
	m.Range(func(fd protoreflect.FieldDescriptor, v protoreflect.Value) bool {
		switch {
		case fd.IsList() && fd.Message() != nil:
			for i, l := 0, v.List(); i < l.Len(); i++ {
				viewMessage(l.Get(i).Message())
			}
		case fd.IsMap() && fd.MapValue().Message() != nil:
			v.Map().Range(func(_ protoreflect.MapKey, mv protoreflect.Value) bool {
				viewMessage(mv.Message())
				return true
			})
		case fd.Message() != nil && !fd.IsMap():
			viewMessage(v.Message())
		}
		return true
	})
}
