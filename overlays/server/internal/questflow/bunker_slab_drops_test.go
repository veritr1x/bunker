package questflow

import (
	"testing"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/model"
)

func TestSlabDrops(t *testing.T) {
	same := func(n int32) int32 { return n }
	// roll returns the values in order, then repeats the last.
	rolls := func(values ...int64) func(int64) int64 {
		return func(n int64) int64 {
			v := values[0]
			if len(values) > 1 {
				values = values[1:]
			}
			if v >= n {
				t.Fatalf("roll %d out of [0, %d)", v, n)
			}
			return v
		}
	}
	main := campaign.QuestTarget{QuestId: 1, QuestType: campaign.QuestTypeMainQuest}
	event := func(eventType int32) campaign.QuestTarget {
		return campaign.QuestTarget{QuestId: 100025, QuestType: campaign.QuestTypeEventQuest, EventQuestType: eventType}
	}
	type slab struct{ id, count int32 }
	cases := []struct {
		name   string
		target campaign.QuestTarget
		rate   func(int32) int32
		roll   func(int64) int64
		want   []slab
	}{
		{"story, fewest", main, same, rolls(0, 1), []slab{{smallSlabFragment, 1}}},
		{"story, most", main, same, rolls(2, 0), []slab{{smallSlabFragment, 3}, {mediumSlabFragment, 1}}},
		{"story, drop rate campaign", main, func(n int32) int32 { return n * 5 / 2 }, rolls(1, 0),
			[]slab{{smallSlabFragment, 5}, {mediumSlabFragment, 2}}},
		{"guerrilla", event(eventQuestTypeGuerrilla), same, rolls(0), []slab{{smallSlabFragment, 1}}},
		{"dungeon", event(eventQuestTypeDungeon), same, rolls(0), []slab{{smallSlabFragment, 1}}},
		{"event story", event(1), same, rolls(0), nil},
		{"Dark Memory", event(7), same, rolls(0), nil},
		{"extra quest", campaign.QuestTarget{QuestId: 1, QuestType: campaign.QuestTypeExtraQuest}, same, rolls(0), nil},
	}
	for _, c := range cases {
		got := slabDrops(c.target, c.rate, c.roll)
		if len(got) != len(c.want) {
			t.Errorf("%s: %+v, want %+v", c.name, got, c.want)
			continue
		}
		for i, d := range got {
			if d.PossessionType != model.PossessionTypeMaterial || d.PossessionId != c.want[i].id || d.Count != c.want[i].count {
				t.Errorf("%s: drop %d is %+v, want %+v", c.name, i, d, c.want[i])
			}
		}
	}
}
