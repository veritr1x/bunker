package masterdata

import (
	"log"

	"lunar-tear/server/internal/bunkercache"
	"lunar-tear/server/internal/utils"
)

// Bunker: what opened each limited-time offer for a player, and for how long.
// The game data has no such table: the server opened a pack when the player
// did something, for a few hours. From the offers' own texts
// (limited.open.achievement.*, limited.open.local.push.*) and notices 10, 140
// and 1063: a Jumpstart pack opens on finishing the loadout tutorial at the
// start of Main Quest chapter 2 (48 hours; from 30 March 2023, 24 hours), a
// completion pack on clearing its chapter at its difficulty (a player who had
// already cleared it gets it at their next login), the Appreciation Gala
// Newcomer Pack for a new player during the gala, and the Mythic Slab
// Material Pack, a guess, when Mythic Slabs unlock (quest 42). The chapters
// come from the packs' names and quest.main.chapter_number.* (The Sun IV: The
// Dawn is chapter 28, Overture I: Indigo chapter 32). With the Original
// calendar each opens on its trigger within its sale period; with everything
// open they all stay open (LimitedOffers).

type LimitedTriggerKind int

const (
	TriggerChapter  LimitedTriggerKind = iota + 1 // Chapter cleared at Difficulty
	TriggerLoadout                                // the chapter 2 loadout tutorial finished (Jumpstart)
	TriggerNewcomer                               // the loadout tutorial finished by a player who began during the sale
	TriggerQuest                                  // Quest cleared
)

type LimitedTrigger struct {
	Kind       LimitedTriggerKind
	Chapter    int32 // MainQuestChapterId
	Difficulty int32 // 1 Normal, 2 Hard, 3 Very Hard
	Quest      int32
	Hours      int64
	// Before and From (original dates, before the calendar's shift) split the
	// Jumpstart packs: the 48-hour pack until 30 March 2023, the 24-hour one after.
	Before, From int64
}

// JumpstartChange is when the 24-hour Jumpstart Pack replaced the 48-hour one
// (notice 1063: 30 March 2023, 18:00 PST).
const JumpstartChange = int64(1680224400000)

// Chapter6PackSale is when the Ch. 6 Completion Pack went on sale (notice 140,
// 1 November 2021); the game data gives every pack the shop's dates from launch.
const Chapter6PackSale = int64(1635733800000)

// LoadoutTutorial is the chapter 2 loadout tutorial (TutorialTypeMenuSecond)
// and the phase it ends on.
const LoadoutTutorial, LoadoutTutorialDone = int32(3), int32(30)

func chapterPacks(chapter, first int32) map[int32]LimitedTrigger {
	out := map[int32]LimitedTrigger{}
	for d := int32(0); d < 3; d++ {
		out[first+d] = LimitedTrigger{Kind: TriggerChapter, Chapter: chapter, Difficulty: d + 1, Hours: 72}
	}
	return out
}

// LimitedTriggers are the offers' triggers by shop item cell.
var LimitedTriggers = func() map[int32]LimitedTrigger {
	t := map[int32]LimitedTrigger{
		140003:  {Kind: TriggerLoadout, Hours: 48, Before: JumpstartChange},                           // 48-Hour Jumpstart Pack
		140295:  {Kind: TriggerLoadout, Hours: 24, From: JumpstartChange},                             // 24-Hour Only Jumpstart Pack
		140319:  {Kind: TriggerNewcomer, Hours: 72},                                                   // Appreciation Gala Newcomer Pack
		9100101: {Kind: TriggerChapter, Chapter: 7, Difficulty: 1, Hours: 72, From: Chapter6PackSale}, // Ch. 6 Inscriptions in Stone
		140008:  {Kind: TriggerChapter, Chapter: 14, Difficulty: 1, Hours: 72},                        // Ch. 12 White Autumn
		140299:  {Kind: TriggerChapter, Chapter: 32, Difficulty: 1, Hours: 24},                        // Overture I: Indigo
		140312:  {Kind: TriggerChapter, Chapter: 33, Difficulty: 1, Hours: 24},                        // Overture II: Scarlet
		140332:  {Kind: TriggerChapter, Chapter: 34, Difficulty: 1, Hours: 24},                        // Overture III: Emerald
		140364:  {Kind: TriggerChapter, Chapter: 35, Difficulty: 1, Hours: 24},                        // Overture IV: Amber
		9200001: {Kind: TriggerQuest, Quest: 42, Hours: 72},                                           // Mythic Slab Material Pack (guess: Mythic Slabs unlock)
	}
	for _, packs := range []map[int32]LimitedTrigger{
		chapterPacks(16, 140045), // The Sun I: The Dawn
		chapterPacks(24, 140048), // The Moon I: The Gloaming
		chapterPacks(28, 140175), // The Sun IV: The Dawn
		chapterPacks(20, 140178), // The Moon IV: The Gloaming
		chapterPacks(29, 140214), // The Sun V: Noontide
		chapterPacks(21, 140217), // The Moon V: Eventide
		chapterPacks(30, 140250), // The Sun VI: Twilight
		chapterPacks(22, 140253), // The Moon VI: Daybreak
	} {
		for k, v := range packs {
			t[k] = v
		}
	}
	return t
}()

// ChapterQuests are a main quest chapter's quests at each difficulty.
var ChapterQuests = bunkercache.Value(func() map[[2]int32][]int32 {
	chapters, err := utils.ReadTable[EntityMMainQuestChapter]("m_main_quest_chapter")
	if err != nil {
		log.Printf("[LimitedOpen] m_main_quest_chapter: %v", err)
	}
	groups, _ := utils.ReadTable[EntityMMainQuestSequenceGroup]("m_main_quest_sequence_group")
	sequences, _ := utils.ReadTable[EntityMMainQuestSequence]("m_main_quest_sequence")
	quests := map[int32][]int32{}
	for _, s := range sequences {
		quests[s.MainQuestSequenceId] = append(quests[s.MainQuestSequenceId], s.QuestId)
	}
	byGroup := map[int32][]EntityMMainQuestSequenceGroup{}
	for _, g := range groups {
		byGroup[g.MainQuestSequenceGroupId] = append(byGroup[g.MainQuestSequenceGroupId], g)
	}
	out := map[[2]int32][]int32{}
	for _, c := range chapters {
		for _, g := range byGroup[c.MainQuestSequenceGroupId] {
			out[[2]int32{c.MainQuestChapterId, g.DifficultyType}] = append(out[[2]int32{c.MainQuestChapterId, g.DifficultyType}], quests[g.MainQuestSequenceId]...)
		}
	}
	return out
})
