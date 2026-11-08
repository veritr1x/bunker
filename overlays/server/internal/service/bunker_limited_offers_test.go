package service

import (
	"context"
	"strings"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/userdata"
)

const hour = int64(3_600_000)

func offerOf(t *testing.T, cell int32) masterdata.LimitedOffer {
	t.Helper()
	offers, _ := masterdata.LimitedOffers()
	for _, o := range offers {
		if o.ShopItemCellId == cell {
			return o
		}
	}
	t.Fatalf("no limited offer for cell %d", cell)
	return masterdata.LimitedOffer{}
}

func clearChapter(u *store.UserState, chapter, difficulty int32) {
	for _, q := range masterdata.ChapterQuests()[[2]int32{chapter, difficulty}] {
		u.Quests[q] = store.UserQuestState{QuestId: q, ClearCount: 1}
	}
}

func buyer(holder *runtime.Holder, users *memUsers) func(o masterdata.LimitedOffer) error {
	srv := NewShopServiceServer(users, users, holder)
	return func(o masterdata.LimitedOffer) error {
		_, err := srv.CreatePurchaseTransaction(context.Background(), &pb.CreatePurchaseTransactionRequest{ShopId: o.ShopId, ShopItemId: o.ShopItemId})
		return err
	}
}

// With the Original calendar a completion pack opens when its chapter is
// cleared, for its hours; the other packs stay closed.
func TestACompletionPackOpensWhenItsChapterIsCleared(t *testing.T) {
	holder, users := harness(t)
	ch12, sun1 := offerOf(t, 140008), offerOf(t, 140045)
	now := ch12.OpenDatetime + 30*24*hour
	setClock(t, now)
	u := &users.user
	OpenLimitedOffers(u, now)
	if len(u.Ext.LimitedOpens) != 0 {
		t.Fatalf("opened %v with nothing cleared", u.Ext.LimitedOpens)
	}
	clearChapter(u, 14, 1)
	OpenLimitedOffers(u, now)
	if got := u.Ext.LimitedOpens[140008]; got != (store.LimitedOpenState{Open: now, Close: now + 72*hour}) {
		t.Fatalf("Ch. 12 pack %+v", got)
	}
	if _, ok := u.Ext.LimitedOpens[140045]; ok {
		t.Fatal("The Sun I pack opened without its chapter")
	}
	rows := userdata.ProjectTables(*u, []string{"IUserLimitedOpen"})["IUserLimitedOpen"]
	if !strings.Contains(rows, `"targetId":140008`) || strings.Contains(rows, `"targetId":140045`) {
		t.Fatalf("IUserLimitedOpen: %.400s", rows)
	}
	buy := buyer(holder, users)
	if buy(sun1) == nil {
		t.Fatal("bought a pack that never opened")
	}
	if err := buy(ch12); err != nil {
		t.Fatalf("open pack: %v", err)
	}
	if buy(ch12) == nil {
		t.Fatal("bought a pack twice")
	}
	setClock(t, now+73*hour)
	OpenLimitedOffers(u, now+73*hour)
	if u.Ext.LimitedOpens[140008].Open != now {
		t.Fatal("a pack opened again")
	}
}

func TestAHardPackNeedsTheHardChapter(t *testing.T) {
	_, users := harness(t)
	o := offerOf(t, 140176) // The Sun IV (Hard) Pack
	now := o.OpenDatetime + hour
	setClock(t, now)
	u := &users.user
	clearChapter(u, 28, 1)
	OpenLimitedOffers(u, now)
	if _, ok := u.Ext.LimitedOpens[140176]; ok {
		t.Fatal("the Hard pack opened on Normal")
	}
	if _, ok := u.Ext.LimitedOpens[140175]; !ok {
		t.Fatal("the Normal pack did not open")
	}
	clearChapter(u, 28, 2)
	OpenLimitedOffers(u, now)
	if _, ok := u.Ext.LimitedOpens[140176]; !ok {
		t.Fatal("the Hard pack did not open")
	}
}

// The Ch. 6 Completion Pack went on sale on 1 November 2021 (notice 140).
func TestTheChapter6PackOpensFromItsNotice(t *testing.T) {
	_, users := harness(t)
	u := &users.user
	clearChapter(u, 7, 1)
	before := masterdata.Chapter6PackSale - 24*hour
	setClock(t, before)
	OpenLimitedOffers(u, before)
	if _, ok := u.Ext.LimitedOpens[9100101]; ok {
		t.Fatal("the Ch. 6 pack opened before its sale")
	}
	after := masterdata.Chapter6PackSale + hour
	setClock(t, after)
	OpenLimitedOffers(u, after)
	if got := u.Ext.LimitedOpens[9100101]; got != (store.LimitedOpenState{Open: after, Close: after + 72*hour}) {
		t.Fatalf("Ch. 6 pack %+v", got)
	}
}

func TestNothingOpensOutsideItsSalePeriod(t *testing.T) {
	_, users := harness(t)
	o := offerOf(t, 140008)
	now := o.CloseDatetime + hour
	setClock(t, now)
	clearChapter(&users.user, 14, 1)
	OpenLimitedOffers(&users.user, now)
	if len(users.user.Ext.LimitedOpens) != 0 {
		t.Fatalf("opened %v after the sale", users.user.Ext.LimitedOpens)
	}
}

// The Jumpstart pack opens from the loadout tutorial's end: the 48-hour pack
// before 30 March 2023, the 24-hour one after. A veteran who finished it long
// ago gets one already closed.
func TestJumpstartOpensFromTheLoadoutTutorial(t *testing.T) {
	harness(t)
	for _, c := range []struct {
		done         int64
		open, closed int32
		hours        int64
	}{{masterdata.JumpstartChange - 10*24*hour, 140003, 140295, 48}, {masterdata.JumpstartChange + 10*24*hour, 140295, 140003, 24}} {
		u := store.SeedUserState(1, "u", 0, model.DefaultPlatform)
		u.Tutorials[masterdata.LoadoutTutorial] = store.TutorialProgressState{TutorialType: masterdata.LoadoutTutorial, ProgressPhase: masterdata.LoadoutTutorialDone, LatestVersion: c.done}
		now := c.done + hour
		setClock(t, now)
		OpenLimitedOffers(u, now)
		if got := u.Ext.LimitedOpens[c.open]; got != (store.LimitedOpenState{Open: c.done, Close: c.done + c.hours*hour}) {
			t.Fatalf("tutorial done %d: pack %d %+v", c.done, c.open, got)
		}
		if _, ok := u.Ext.LimitedOpens[c.closed]; ok {
			t.Fatalf("tutorial done %d: the other Jumpstart pack %d opened", c.done, c.closed)
		}
	}
}

// With everything open every pack stays open (the game data keeps them).
func TestEverythingOpenListsEveryOffer(t *testing.T) {
	_, users := harness(t)
	gametime.SetCalendar(nil)
	offers, _ := masterdata.LimitedOffers()
	OpenLimitedOffers(&users.user, offers[0].OpenDatetime+hour)
	if len(users.user.Ext.LimitedOpens) != 0 {
		t.Fatal("triggers recorded with the calendar off")
	}
	rows := userdata.ProjectTables(users.user, []string{"IUserLimitedOpen"})["IUserLimitedOpen"]
	if strings.Count(rows, `"limitedOpenTargetType":5`) != len(offers) {
		t.Fatalf("%d offers listed, want %d", strings.Count(rows, `"limitedOpenTargetType":5`), len(offers))
	}
}

func TestEveryOfferHasATrigger(t *testing.T) {
	harness(t)
	offers, _ := masterdata.LimitedOffers()
	for _, o := range offers {
		if _, ok := masterdata.LimitedTriggers[o.ShopItemCellId]; !ok {
			t.Errorf("offer cell %d (shop item %d) has no trigger", o.ShopItemCellId, o.ShopItemId)
		}
	}
	for cell, tr := range masterdata.LimitedTriggers {
		if tr.Kind == masterdata.TriggerChapter && len(masterdata.ChapterQuests()[[2]int32{tr.Chapter, tr.Difficulty}]) == 0 {
			t.Errorf("cell %d: chapter %d difficulty %d has no quests", cell, tr.Chapter, tr.Difficulty)
		}
	}
}
