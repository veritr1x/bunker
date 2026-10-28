package service

// The Original calendar replays an Abyss Tower's runs as copies of its chapter
// (the chapter + n * 10,000,000, android_calendar.py COPY_STEP). The tower's
// accumulation rewards are claimed once across its runs, as in the live game,
// where every run was the same chapter.
const towerRunStep = 10_000_000

func towerBase(chapterId int32) int32 { return chapterId % towerRunStep }
