package questflow

import (
	"testing"

	"lunar-tear/server/internal/model"
)

func TestChapterMemoirDrop(t *testing.T) {
	set := []int32{8016, 8031, 8046}
	double := func(n int32) int32 { return 2 * n }
	roll := func(values ...int64) func(int64) int64 {
		return func(n int64) int64 {
			v := values[0]
			values = values[1:]
			if v >= n {
				t.Fatalf("roll %d out of [0, %d)", v, n)
			}
			return v
		}
	}
	if d := chapterMemoirDrop(set, double, roll(1)); d != nil {
		t.Fatalf("dropped on a miss: %+v", d)
	}
	d := chapterMemoirDrop(set, double, roll(0, 2))
	if len(d) != 1 || d[0] != (RewardGrant{PossessionType: model.PossessionTypeParts, PossessionId: 8046, Count: 2}) {
		t.Fatalf("drop %+v", d)
	}
	if d := chapterMemoirDrop(nil, double, roll()); d != nil {
		t.Fatalf("dropped without a set: %+v", d)
	}
}
