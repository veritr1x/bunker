package masterdata

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"lunar-tear/server/internal/masterdata/memorydb"
)

func TestChapterMemoirsAreTheAdvertisedOnesNoQuestDrops(t *testing.T) {
	const parts = 4
	got := chapterMemoirs(chapterMemoirTables{
		chapters:     []EntityMEventQuestChapter{{EventQuestChapterId: 1, EventQuestDisplayItemGroupId: 10, EventQuestSequenceGroupId: 20}},
		display:      []EntityMEventQuestDisplayItemGroup{{EventQuestDisplayItemGroupId: 10, PossessionType: parts, PossessionId: 140}, {EventQuestDisplayItemGroupId: 10, PossessionType: parts, PossessionId: 230}, {EventQuestDisplayItemGroupId: 10, PossessionType: parts, PossessionId: 110}, {EventQuestDisplayItemGroupId: 10, PossessionType: 6, PossessionId: 1}},
		groups:       []EntityMEventQuestSequenceGroup{{EventQuestSequenceGroupId: 20, EventQuestSequenceId: 30}},
		sequences:    []EntityMEventQuestSequence{{EventQuestSequenceId: 30, QuestId: 500}, {EventQuestSequenceId: 30, QuestId: 501}},
		quests:       []EntityMQuest{{QuestId: 500, QuestPickupRewardGroupId: 60}, {QuestId: 501, QuestPickupRewardGroupId: 61}},
		pickups:      []EntityMQuestPickupRewardGroup{{QuestPickupRewardGroupId: 60, BattleDropRewardId: 70}, {QuestPickupRewardGroupId: 61, BattleDropRewardId: 71}},
		battleDrops:  []EntityMBattleDropReward{{BattleDropRewardId: 70, PossessionType: parts, PossessionId: 111}, {BattleDropRewardId: 71, PossessionType: 6, PossessionId: 2}},
		partsEntries: []EntityMParts{{PartsId: 140, PartsGroupId: 1, RarityType: 40}, {PartsId: 230, PartsGroupId: 2, RarityType: 30}, {PartsId: 110, PartsGroupId: 1, RarityType: 10}, {PartsId: 111, PartsGroupId: 1, RarityType: 10}},
	})
	// 110 is group 1 at rarity 10, which quest 500 drops (as 111, another rank).
	want := map[int32][]int32{500: {140, 230}, 501: {140, 230}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestChapterMemoirsOnTheGameData(t *testing.T) {
	master := os.Getenv("BUNKER_TEST_MASTER")
	if master == "" {
		t.Skip("BUNKER_TEST_MASTER not set")
	}
	path := filepath.Join(t.TempDir(), "master.bin.e")
	data, err := os.ReadFile(master)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := memorydb.Init(path); err != nil {
		t.Fatal(err)
	}
	all := ChapterMemoirs()
	// Chapter 300's quests drop memoir series 401 at rarity 10 and 20; the
	// chapter shows 401 at 40, 402 at 30 and 403 at 20.
	if got := all[220001]; !reflect.DeepEqual(got, []int32{8016, 8031, 8046}) {
		t.Fatalf("quest 220001: %v", got)
	}
	// 25 chapters of 6 to 10 quests each.
	if len(all) < 150 || len(all) > 300 {
		t.Fatalf("%d quests with chapter memoirs", len(all))
	}
}
