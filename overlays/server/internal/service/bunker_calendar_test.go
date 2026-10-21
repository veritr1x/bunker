package service

import (
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
)

// Runs on the original master data (BUNKER_TEST_MASTER), whose event dates
// are all in the past.
func loadMaster(t *testing.T) *runtime.Holder {
	return loadMasterFile(t, os.Getenv("BUNKER_TEST_MASTER"))
}

func loadMasterFile(t *testing.T, master string) *runtime.Holder {
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
	h, err := runtime.NewHolder(path)
	if err != nil {
		t.Fatal(err)
	}
	return h
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

// Leftover shards become Medals once, at the medal's AutoConvertDatetime.
func TestShardsConvertIntoMedals(t *testing.T) {
	cats := loadMaster(t).Get()
	info := cats.GachaHandler.MedalInfo[45]
	if info.AutoConvertDatetime == 0 || info.AutoConvertDatetime > 2_000_000_000_000 {
		t.Skip("needs the original master data")
	}
	u := store.UserState{ConsumableItems: map[int32]int32{info.ConsumableItemId: 170, 2: 5}}
	u.EnsureMaps()
	u.Gacha.BannerStates[45] = store.GachaBannerState{MedalCount: 12}
	autoConvertExpiredMedals(&u, cats.GachaEntries, cats.GachaHandler, info.AutoConvertDatetime-1)
	if u.ConsumableItems[info.ConsumableItemId] != 170 {
		t.Fatal("converted before AutoConvertDatetime")
	}
	autoConvertExpiredMedals(&u, cats.GachaEntries, cats.GachaHandler, info.AutoConvertDatetime)
	rate := max(info.ConversionRate, 1)
	if _, left := u.ConsumableItems[info.ConsumableItemId]; left || u.ConsumableItems[2] != 5+170*rate {
		t.Fatalf("after conversion: shards %d, Medals %d", u.ConsumableItems[info.ConsumableItemId], u.ConsumableItems[2])
	}
	c := u.Gacha.ConvertedGachaMedal
	if len(c.ConvertedMedalPossession) != 1 || c.ConvertedMedalPossession[0].Count != 170 || c.ObtainPossession == nil || c.ObtainPossession.Count != 170*rate {
		t.Fatalf("conversion record %+v", c)
	}
	if u.Gacha.BannerStates[45].MedalCount != 0 || u.Gacha.BannerStates[46].MedalCount != 0 {
		t.Fatal("banner medal counts kept")
	}
	autoConvertExpiredMedals(&u, cats.GachaEntries, cats.GachaHandler, info.AutoConvertDatetime+1)
	if u.ConsumableItems[2] != 5+170*rate {
		t.Fatal("converted twice")
	}
}

func TestGachaCatalogEntries(t *testing.T) {
	cats := loadMaster(t).Get()
	seen := map[int32]int{}
	for _, e := range cats.GachaEntries {
		seen[e.GachaId]++
		for _, p := range e.PricePhases {
			// Premium summons take the Premium Summon Ticket; the ticket summons
			// (confirm_*: ★★★+ and ★★★★ guaranteed) and Mama's Dream take their own.
			_, prizeBox := masterdata.PrizeBoxFor(e.GachaId)
			if e.GachaLabelType == model.GachaLabelPremium && p.PriceType == model.PriceTypeConsumableItem && p.PriceId != 1002 &&
				!strings.HasPrefix(e.BannerAssetName, "confirm_") && !prizeBox {
				t.Fatalf("summon %d ticket phase costs item %d", e.GachaId, p.PriceId)
			}
		}
	}
	for id, n := range seen {
		if n > 1 {
			t.Errorf("summon %d listed %d times", id, n)
		}
	}
	medals := map[int32]int32{}
	for _, m := range table[masterdata.EntityMGachaMedal]("m_gacha_medal") {
		medals[m.ShopTransitionGachaId] = m.CeilingCount
	}
	for _, e := range cats.GachaEntries {
		if want, ok := medals[e.GachaId]; ok && want > 0 && e.CeilingCount != want {
			t.Errorf("summon %d ceiling %d, medal says %d", e.GachaId, e.CeilingCount, want)
		}
	}
}

// With the calendar's game data the featured items match the original's.
// BUNKER_TEST_CALENDAR_MASTER is a calendar build of BUNKER_TEST_MASTER and
// BUNKER_TEST_CALENDAR_START its loop start.
func TestCalendarFeaturedMatchesOriginal(t *testing.T) {
	path, start := os.Getenv("BUNKER_TEST_CALENDAR_MASTER"), os.Getenv("BUNKER_TEST_CALENDAR_START")
	if path == "" || start == "" {
		t.Skip("BUNKER_TEST_CALENDAR_MASTER and BUNKER_TEST_CALENDAR_START not set")
	}
	original := loadMaster(t).Get().GachaHandler.Pool.FeaturedByGacha
	loopStart, _ := strconv.ParseInt(start, 10, 64)
	gametime.SetCalendar(&gametime.Calendar{Loop: 1, LoopStart: loopStart, Speed: 1})
	defer gametime.SetCalendar(nil)
	shifted := loadMasterFile(t, path).Get().GachaHandler.Pool.FeaturedByGacha
	if len(original) == 0 || len(shifted) != len(original) {
		t.Fatalf("featured summons: original %d, calendar %d", len(original), len(shifted))
	}
	for id, f := range original {
		g := shifted[id]
		if len(g.Costumes) != len(f.Costumes) || len(g.Weapons) != len(f.Weapons) {
			t.Errorf("summon %d featured differs under the calendar", id)
		}
	}
}
