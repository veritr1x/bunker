package service

import (
	"context"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// The game shows every summon it is sent as open (it never reads
// IsUserGachaUnlock), so a chapter summon is listed only once its quest is
// cleared.
func TestChapterSummonListedWhenUnlocked(t *testing.T) {
	holder, users := harness(t)
	cat := holder.Get()
	var entry store.GachaCatalogEntry
	for _, e := range cat.GachaEntries {
		if e.GachaLabelType == model.GachaLabelChapter && e.UnlockConditionType == model.GachaUnlockMainQuestClear {
			entry = e
			break
		}
	}
	if entry.GachaId == 0 {
		t.Fatal("no chapter summon with an unlock quest")
	}
	setClock(t, entry.StartDatetime+1)
	srv := NewGachaServiceServer(users, users, holder)
	listed := func() bool {
		resp, err := srv.GetGachaList(context.Background(), &pb.GetGachaListRequest{GachaLabelType: []int32{model.GachaLabelChapter}})
		if err != nil {
			t.Fatal(err)
		}
		for _, g := range resp.Gacha {
			if g.GachaId == entry.GachaId {
				return true
			}
		}
		return false
	}
	if listed() {
		t.Fatalf("chapter summon %d listed before quest %d is cleared", entry.GachaId, entry.UnlockConditionValue)
	}
	q := entry.UnlockConditionValue
	users.user.Quests[q] = store.UserQuestState{QuestId: q, QuestStateType: model.UserQuestStateTypeCleared, ClearCount: 1}
	if !listed() {
		t.Fatalf("chapter summon %d not listed after quest %d is cleared", entry.GachaId, q)
	}
}
