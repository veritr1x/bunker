package missions

import (
	"testing"

	"lunar-tear/server/internal/store"
)

// A quest and its earlier runs' copies share their progress (store.LinkQuests),
// so one clear raises every clear count of the family: it counts once, for the
// quest played, whose chapter is the run's.
func TestAClearOfARunsCopyCountsOnce(t *testing.T) {
	const copy = 200583 + 1_000_000_000
	store.SetQuestCopies([]int32{200583, copy})
	defer store.SetQuestCopies(nil)
	quests := func(n int32) map[int32]store.UserQuestState {
		return map[int32]store.UserQuestState{200583: {QuestId: 200583, ClearCount: n}, copy: {QuestId: copy, ClearCount: n}}
	}
	before := &store.UserState{Quests: quests(1)}
	before.EventQuest.CurrentQuestId = copy
	after := &store.UserState{Quests: quests(2)} // finishing cleared the event quest in play
	c := collect(before, after, "/apb.api.quest.QuestService/FinishEventQuest", nil)
	if len(c.clears) != 1 || c.clears[0].questId != copy || c.clears[0].count != 1 {
		t.Fatalf("clears %+v", c.clears)
	}
	before.EventQuest.CurrentQuestId = 0 // a clear with no event quest in play: the first member whose count rose
	c = collect(before, after, "", nil)
	if len(c.clears) != 1 {
		t.Fatalf("clears %+v", c.clears)
	}
}
