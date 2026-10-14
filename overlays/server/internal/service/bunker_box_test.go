package service

import (
	"testing"

	"lunar-tear/server/internal/gacha"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

func TestChapterSummonBox(t *testing.T) {
	holder, users := harness(t)
	cat := holder.Get()
	var entry store.GachaCatalogEntry
	for _, e := range cat.GachaEntries {
		if e.GachaLabelType == model.GachaLabelChapter && len(e.BoxContents) > 0 {
			entry = e
			break
		}
	}
	if entry.GachaId == 0 {
		t.Fatal("no chapter summon with a box")
	}
	total, targets := int32(0), 0
	for _, c := range entry.BoxContents {
		total += c.Count
		if c.IsTarget {
			targets++
		}
	}
	if targets == 0 || total < 10 {
		t.Fatalf("box %+v", entry.BoxContents)
	}
	one := entry.PricePhases[0]
	u := &users.user
	u.ConsumableItems[one.PriceId] = total + 5
	now := int64(1_800_000_000_000)
	setClock(t, now)

	if err := cat.GachaHandler.HandleResetBox(u, entry); err == nil {
		t.Fatal("a full box was reset")
	}
	got := map[int32]int32{}
	for i := int32(0); i < total; i++ {
		res, err := cat.GachaHandler.HandleDraw(u, entry, one.PhaseId, 1)
		if err != nil {
			t.Fatalf("draw %d of %d: %v", i+1, total, err)
		}
		for _, it := range res.Items {
			got[it.PossessionId]++
		}
	}
	for _, c := range entry.BoxContents {
		if got[c.PossessionId] != c.Count {
			t.Fatalf("drew %d of material %d, box has %d", got[c.PossessionId], c.PossessionId, c.Count)
		}
	}
	if _, err := cat.GachaHandler.HandleDraw(u, entry, one.PhaseId, 1); err == nil {
		t.Fatal("drew from an empty box")
	}
	if u.ConsumableItems[one.PriceId] != 5 {
		t.Fatalf("tickets left %d, want 5 (a refused draw is free)", u.ConsumableItems[one.PriceId])
	}
	if !gacha.Box(u, entry, now).TargetsDrawn {
		t.Fatal("targets not drawn")
	}
	if err := cat.GachaHandler.HandleResetBox(u, entry); err != nil {
		t.Fatal(err)
	}
	if left := gacha.Box(u, entry, now).Left; left != total {
		t.Fatalf("after reset %d left, want %d", left, total)
	}
	// A new month refills the box.
	cat.GachaHandler.HandleDraw(u, entry, one.PhaseId, 1)
	if left := gacha.Box(u, entry, now+40*86400000).Left; left != total {
		t.Fatalf("next month %d left, want %d", left, total)
	}
}
