package model

// GachaUnlockDarkMemories is Bunker's own summon unlock condition, never sent
// to the game: open once Dark Memories are, as the game decides it
// (CalculatorEndContents.IsUnlockEndContents: the END_CONTENTS tutorial at
// EndContentsFirst, written by the unlock scene after the first Hard chapter).
const GachaUnlockDarkMemories int32 = 1001

// TutorialPhaseEndContentsFirst is TutorialPhases.EndContentsFirst.
const TutorialPhaseEndContentsFirst int32 = 10

// GachaUnlockEventRun is Bunker's own condition for event summons, never sent
// to the game: open while one of the event's runs is (plus the summons' two
// days of grace); masterdata.EventSummonRunAt.
const GachaUnlockEventRun int32 = 1002
