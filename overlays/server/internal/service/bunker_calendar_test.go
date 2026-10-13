package service

import (
	"io"
	"os"
	"path/filepath"
	"testing"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
)

// Runs on the original master data (BUNKER_TEST_MASTER), whose event dates
// are all in the past.
func loadMaster(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	path := filepath.Join(t.TempDir(), "master.bin.e")
	in, err := os.Open(master)
	if err != nil {
		t.Fatal(err)
	}
	out, _ := os.Create(path)
	io.Copy(out, in)
	in.Close()
	out.Close()
	if _, err := runtime.NewHolder(path); err != nil {
		t.Fatal(err)
	}
}

func TestCalendarGameStart(t *testing.T) {
	loadMaster(t)
	defer gametime.SetCalendar(nil)
	now := int64(1_800_000_000_000) // 2027, after every original term

	// An event item with a term, a summon medal with a term, a permanent item.
	terms := map[int32]bool{}
	for _, tm := range table[masterdata.EntityMConsumableItemTerm]("m_consumable_item_term") {
		terms[tm.ConsumableItemTermId] = tm.EndDatetime < now
	}
	medals := map[int32]bool{}
	for _, m := range table[masterdata.EntityMGachaMedal]("m_gacha_medal") {
		medals[m.ConsumableItemId] = true
	}
	var event, medal, permanent int32
	for _, it := range table[masterdata.EntityMConsumableItem]("m_consumable_item") {
		switch {
		case it.ConsumableItemTermId != 0 && terms[it.ConsumableItemTermId] && medals[it.ConsumableItemId] && medal == 0:
			medal = it.ConsumableItemId
		case it.ConsumableItemTermId != 0 && terms[it.ConsumableItemTermId] && !medals[it.ConsumableItemId] && event == 0:
			event = it.ConsumableItemId
		case it.ConsumableItemTermId == 0 && permanent == 0:
			permanent = it.ConsumableItemId
		}
	}
	if event == 0 || permanent == 0 {
		t.Skip("needs the original master data, where item terms end")
	}
	u := store.UserState{ConsumableItems: map[int32]int32{event: 5, permanent: 7}}
	if medal != 0 {
		u.ConsumableItems[medal] = 3
	}

	// Calendar off: nothing changes.
	calendarGameStart(&u, now)
	if u.ConsumableItems[event] != 5 || u.Ext.CalendarLoop != 0 {
		t.Fatal("calendar off changed the save")
	}

	gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: 1, Speed: 1})
	calendarGameStart(&u, now)
	if _, ok := u.ConsumableItems[event]; ok || u.ConsumableItems[permanent] != 7 {
		t.Fatalf("expiry: %v", u.ConsumableItems)
	}
	if medal != 0 && u.ConsumableItems[medal] != 3 {
		t.Fatal("summon medal removed before it converts")
	}
	if u.Ext.CalendarLoop != 1 {
		t.Fatalf("joined loop %d", u.Ext.CalendarLoop)
	}

	// A rotating event chapter's quest and a rotating shop's item.
	var eventQuest int32
	groups := map[int32]int32{}
	for _, g := range table[masterdata.EntityMEventQuestSequenceGroup]("m_event_quest_sequence_group") {
		groups[g.EventQuestSequenceGroupId] = g.EventQuestSequenceId
	}
	for _, ch := range table[masterdata.EntityMEventQuestChapter]("m_event_quest_chapter") {
		if ch.EndDatetime < neverEnds && eventQuest == 0 {
			for _, s := range table[masterdata.EntityMEventQuestSequence]("m_event_quest_sequence") {
				if s.EventQuestSequenceId == groups[ch.EventQuestSequenceGroupId] {
					eventQuest = s.QuestId
					break
				}
			}
		}
	}
	u.Quests = map[int32]store.UserQuestState{eventQuest: {QuestId: eventQuest, ClearCount: 1}, 1: {QuestId: 1, ClearCount: 1}}
	u.Ext.MissionPass = map[int32]store.MissionPassPointState{1: {MissionPassId: 1, Point: 900}}
	u.Ext.Pvp.Point = 1234

	// The same loop keeps progress; the next loop resets what reruns.
	calendarGameStart(&u, now)
	if len(u.Quests) != 2 {
		t.Fatal("progress reset within a loop")
	}
	gametime.SetCalendar(&gametime.Calendar{Loop: 2, LoopStart: 1, Speed: 1})
	calendarGameStart(&u, now)
	if _, ok := u.Quests[eventQuest]; ok || u.Quests[1].ClearCount != 1 {
		t.Fatalf("event quest %d not reset or main quest lost: %v", eventQuest, u.Quests)
	}
	if len(u.Ext.MissionPass) != 0 || u.Ext.CalendarLoop != 2 || u.Ext.Pvp.Point != 1234 {
		t.Fatalf("loop 2: pass %v loop %d arena %d", u.Ext.MissionPass, u.Ext.CalendarLoop, u.Ext.Pvp.Point)
	}
}

func TestAutomataVol2SharesShards(t *testing.T) {
	loadMaster(t)
	entries, medals, err := masterdata.LoadGachaCatalog()
	if err != nil {
		t.Fatal(err)
	}
	byId := map[int32]store.GachaCatalogEntry{}
	for _, e := range entries {
		byId[e.GachaId] = e
	}
	for vol2, vol1 := range map[int32]int32{46: 45, 151: 150} {
		a, b := byId[vol1], byId[vol2]
		if b.GachaId == 0 || b.MedalConsumableItemId == 0 || b.MedalConsumableItemId != a.MedalConsumableItemId {
			t.Errorf("summon %d not offered with summon %d's medal: %+v", vol2, vol1, b)
		}
		if medals[vol2] != medals[vol1] {
			t.Errorf("summon %d medal info differs", vol2)
		}
	}
}
