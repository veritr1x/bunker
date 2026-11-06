package questflow

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/mods"
	"lunar-tear/server/internal/store"
)

// Mods changes are in use at once in tests.
func init() { mods.Recheck = 0 }

func useMods(t *testing.T, body string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "mods.json")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	mods.SetPath(path)
	t.Cleanup(func() { mods.SetPath("") })
}

func drops() []RewardGrant {
	return []RewardGrant{
		{PossessionType: model.PossessionTypeConsumableItem, PossessionId: 1, Count: 2},
		{PossessionType: model.PossessionTypeFreeGem, Count: 5},
		{PossessionType: model.PossessionTypeParts, PossessionId: 3, Count: 1},
		{PossessionType: model.PossessionTypeCostume, PossessionId: 4, Count: 1},
		{PossessionType: model.PossessionTypeImportantItem, PossessionId: 5, Count: 1},
	}
}

func TestTheMultiplierScalesItemsGemsAndGoldOnly(t *testing.T) {
	useMods(t, `{"rewardMultiplier": 3}`)
	got := modScaleDrops(drops(), campaign.QuestTarget{QuestType: campaign.QuestTypeMainQuest})
	want := []int32{6, 15, 1, 1, 1}
	for i, d := range got {
		if d.Count != want[i] {
			t.Fatalf("drop %d (%v) = %d, want %d", i, d.PossessionType, d.Count, want[i])
		}
	}
	if g := modScaleGold(100); g != 300 {
		t.Fatalf("gold = %d", g)
	}
}

func TestDarkMemoryQuestsAndNoModKeepTheirRewards(t *testing.T) {
	useMods(t, `{"rewardMultiplier": 10}`)
	dark := campaign.QuestTarget{QuestType: campaign.QuestTypeEventQuest, EventQuestType: eventQuestTypeEndContents}
	for i, d := range modScaleDrops(drops(), dark) {
		if d.Count != drops()[i].Count {
			t.Fatalf("Dark Memory drop %d multiplied", i)
		}
	}
	useMods(t, `{}`)
	for i, d := range modScaleDrops(drops(), campaign.QuestTarget{}) {
		if d.Count != drops()[i].Count {
			t.Fatalf("drop %d multiplied with the mod off", i)
		}
	}
	if modScaleGold(100) != 100 {
		t.Fatal("gold multiplied with the mod off")
	}
}

func TestUnlimitedDailyPlaysDoesNotCount(t *testing.T) {
	useMods(t, `{"unlimitedDailyPlays": true}`)
	var q store.UserQuestState
	addDailyClears(&q, 3, 5000)
	if q.DailyClearCount != 0 || q.LastClearDatetime != 5000 {
		t.Fatalf("with the mod: %+v", q)
	}
	useMods(t, `{}`)
	addDailyClears(&q, 3, 6000)
	if q.DailyClearCount != 3 {
		t.Fatalf("without the mod: %+v", q)
	}
}

func TestFreeSkipsSpendNoTickets(t *testing.T) {
	setup := func(tickets int32) (*QuestHandler, *store.UserState) {
		h := testHandler()
		h.QuestById[testQuest] = masterdata.EntityMQuest{QuestId: testQuest, Stamina: 1}
		h.MaxStaminaByLevel = map[int32]int32{1: 50}
		u := testUser()
		u.Status.Level = 1
		u.Status.StaminaMilliValue = 50000
		u.ConsumableItems[2003] = tickets
		return h, u
	}
	useMods(t, `{"freeSkips": true}`)
	for _, tickets := range []int32{0, 1} {
		h, u := setup(tickets)
		if _, err := h.HandleQuestSkip(u, testQuest, 3, 1, 0); err != nil {
			t.Fatalf("%d tickets: %v", tickets, err)
		}
		if u.ConsumableItems[2003] != tickets || u.Quests[testQuest].ClearCount != 3 {
			t.Fatalf("%d tickets: tickets %d clears %d", tickets, u.ConsumableItems[2003], u.Quests[testQuest].ClearCount)
		}
	}
	useMods(t, `{}`)
	h, u := setup(1)
	if _, err := h.HandleQuestSkip(u, testQuest, 3, 1, 0); !errors.Is(err, ErrSkipRefused) {
		t.Fatalf("without the mod, 3 skips on 1 ticket: %v", err)
	}
}

func TestExpMultiplier(t *testing.T) {
	useMods(t, `{"expMultiplier": 3}`)
	if got := modScaleExp(40); got != 120 {
		t.Fatalf("modScaleExp(40) = %d", got)
	}
	h := testHandler()
	h.QuestById[testQuest] = masterdata.EntityMQuest{QuestId: testQuest, UserExp: 10}
	u := testUser()
	before := u.Status.Exp
	h.applyExpRewards(u, testQuest, 0)
	if got := u.Status.Exp - before; got != 30 && u.Status.Level == 1 {
		t.Fatalf("player EXP +%d, want +30", got)
	}
	useMods(t, `{}`)
	if got := modScaleExp(40); got != 40 {
		t.Fatalf("off: %d", got)
	}
}

func TestChallengeBonusScalesDrops(t *testing.T) {
	useMods(t, `{"hardEnemies": 2}`)
	main := campaign.QuestTarget{QuestType: campaign.QuestTypeMainQuest}
	if got := modScaleDrops(drops(), main)[0].Count; got != 6 {
		t.Fatalf("challenge bonus ×3: item %d, want 6", got)
	}
	if g := modScaleGold(100); g != 300 {
		t.Fatalf("challenge bonus gold %d", g)
	}
	saved := newDayPaused
	t.Cleanup(func() { newDayPaused = saved })
	newDayPaused = func(int64) bool { return true }
	if got := modScaleDrops(drops(), main)[0].Count; got != 2 {
		t.Fatalf("after Start a new day: item %d, want 2", got)
	}
}
