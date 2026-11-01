package questflow

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Scene 2 gives the starter costume and weapons; a repeated report of it
// (the client sends scene progress again after a restart) gave them again.
func TestSceneGrantsOnlyOnFirstArrival(t *testing.T) {
	h := testHandler()
	h.SceneById = map[int32]masterdata.EntityMQuestScene{2: {QuestSceneId: 2, QuestId: testQuest, SortOrder: 2}}
	h.ChapterLastSceneByQuestId = map[int32]int32{testQuest: 9}
	h.SceneGrantsBySceneId = map[int32][]masterdata.EntityMUserQuestSceneGrantPossession{
		2: {{QuestSceneId: 2, PossessionType: int32(model.PossessionTypeWeapon), PossessionId: 100001, Count: 1}},
	}
	u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	h.HandleMainFlowSceneProgress(u, 2, 1)
	h.HandleMainFlowSceneProgress(u, 2, 2)
	if len(u.Weapons) != 1 {
		t.Fatalf("%d starter weapons after two reports of scene 2, want 1", len(u.Weapons))
	}
}
