package service

import (
	"fmt"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func testGift(id string, possType model.PossessionType, possId, count int32, expires int64) store.NotReceivedGiftState {
	return store.NotReceivedGiftState{
		GiftCommon:         store.GiftCommonState{PossessionType: int32(possType), PossessionId: possId, Count: count},
		ExpirationDatetime: expires,
		UserGiftUuid:       id,
	}
}

func TestReceiveGifts(t *testing.T) {
	g := &store.PossessionGranter{Limits: store.PossessionLimits{Material: 99999}}
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	user.Materials[100002] = 99999
	user.Gifts.NotReceived = []store.NotReceivedGiftState{
		testGift("ok", model.PossessionTypeMaterial, 100001, 5, 2000),
		testGift("old", model.PossessionTypeMaterial, 100001, 5, 500),
		testGift("full", model.PossessionTypeMaterial, 100002, 1, 0),
	}
	received, expired, overflow := receiveGifts(user, g, []string{"ok", "old", "full", "missing"}, 100, 1000)
	if fmt.Sprint(received, expired, overflow) != "[ok] [old] [full]" {
		t.Fatalf("received %v expired %v overflow %v", received, expired, overflow)
	}
	if user.Materials[100001] != 5 || len(user.Gifts.NotReceived) != 1 || user.Gifts.NotReceived[0].UserGiftUuid != "full" || len(user.Gifts.Received) != 1 {
		t.Fatalf("materials %d box %v history %d", user.Materials[100001], user.Gifts.NotReceived, len(user.Gifts.Received))
	}
}

func TestGiftListPaging(t *testing.T) {
	var gifts []store.NotReceivedGiftState
	for i := range 5 {
		gifts = append(gifts, testGift(fmt.Sprint(i), model.PossessionTypeMaterial, 1, 1, int64(10000+i%3)))
	}
	gifts = append(gifts, testGift("gem", model.PossessionTypeFreeGem, 0, 1, 20000))
	ids := func(r *pb.GetGiftListResponse) (out []string) {
		for _, g := range r.Gift {
			out = append(out, g.UserGiftUuid)
		}
		return
	}
	for _, asc := range []bool{true, false} {
		req := &pb.GetGiftListRequest{IsAscendingSort: asc, GetCount: 2}
		first := giftListPage(gifts, req, 1, 0)
		if first.TotalPageCount != 3 {
			t.Fatalf("pages %d", first.TotalPageCount)
		}
		var all []string
		page := first
		for len(page.Gift) > 0 {
			all = append(all, ids(page)...)
			page = giftListPage(gifts, &pb.GetGiftListRequest{IsAscendingSort: asc, GetCount: 2, NextCursor: page.NextCursor}, 1, 0)
		}
		if len(all) != 6 {
			t.Fatalf("asc=%v walked %v", asc, all)
		}
		// Previous from the second page returns the first; the client's
		// reload cursor (previous -/+ 1 as next) returns the same page.
		second := giftListPage(gifts, &pb.GetGiftListRequest{IsAscendingSort: asc, GetCount: 2, NextCursor: first.NextCursor}, 1, 0)
		back := giftListPage(gifts, &pb.GetGiftListRequest{IsAscendingSort: asc, GetCount: 2, PreviousCursor: second.PreviousCursor}, 1, 0)
		step := int64(-1)
		if !asc {
			step = 1
		}
		reload := giftListPage(gifts, &pb.GetGiftListRequest{IsAscendingSort: asc, GetCount: 2, NextCursor: second.PreviousCursor + step}, 1, 0)
		if fmt.Sprint(ids(back)) != fmt.Sprint(ids(first)) || fmt.Sprint(ids(reload)) != fmt.Sprint(ids(second)) {
			t.Fatalf("asc=%v first %v back %v second %v reload %v", asc, ids(first), ids(back), ids(second), ids(reload))
		}
	}
	gems := giftListPage(gifts, &pb.GetGiftListRequest{RewardKindType: []int32{giftKindGem}}, 1, 0)
	if fmt.Sprint(ids(gems)) != "[gem]" || gems.TotalPageCount != 1 {
		t.Fatalf("gem filter %v", ids(gems))
	}
	if r := giftListPage(gifts, &pb.GetGiftListRequest{ExpirationType: giftExpirationOnlyNotExpire}, 1, 0); len(r.Gift) != 0 {
		t.Fatalf("no gift lacks an expiration, got %v", ids(r))
	}
}

func TestPruneExpiredGifts(t *testing.T) {
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	user.Gifts.NotReceived = []store.NotReceivedGiftState{
		testGift("live", model.PossessionTypeMaterial, 100001, 1, 2000),
		testGift("old", model.PossessionTypeMaterial, 100001, 1, 500),
		testGift("forever", model.PossessionTypeMaterial, 100001, 1, 0),
	}
	if n := liveGiftCount(user.Gifts.NotReceived, 1000); n != 2 {
		t.Fatalf("live count %d, want 2", n)
	}
	pruneExpiredGifts(user, 1000)
	if len(user.Gifts.NotReceived) != 2 || user.Notifications.GiftNotReceiveCount != 2 {
		t.Fatalf("after prune: %d gifts, count %d", len(user.Gifts.NotReceived), user.Notifications.GiftNotReceiveCount)
	}
}

func TestChapterGachaStaysUnlockedDuringReplay(t *testing.T) {
	entry := store.GachaCatalogEntry{IsUserGachaUnlock: true, UnlockConditionType: model.GachaUnlockMainQuestClear, UnlockConditionValue: 7}
	user := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
	if gachaUnlockedFor(entry, user) {
		t.Fatal("unlocked before the quest was cleared")
	}
	// Replaying a cleared quest sets it back to Active until the run ends.
	user.Quests[7] = store.UserQuestState{QuestId: 7, QuestStateType: model.UserQuestStateTypeActive, ClearCount: 1}
	if !gachaUnlockedFor(entry, user) {
		t.Error("locked while its cleared quest is being replayed")
	}
}
