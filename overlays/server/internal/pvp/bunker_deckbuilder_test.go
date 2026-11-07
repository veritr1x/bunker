package pvp

import (
	"encoding/json"
	"math/rand/v2"
	"os"
	"path/filepath"
	"testing"
)

// With a deck table, the matching list shows the decks the opponents field.
func TestOpponentsShowTheDeckTheyField(t *testing.T) {
	c, u := realSave(t)
	now := seasonTime(c)
	_, ladder, ok := c.Sync(&u, now)
	if !ok {
		t.Skip("no season")
	}
	c.Match(&u.Ext.Pvp, ladder, rand.New(rand.NewPCG(1, 2)))
	dir := t.TempDir()
	b, _ := json.Marshal(testTable(30))
	if err := os.WriteFile(filepath.Join(dir, deckFile), b, 0o644); err != nil {
		t.Fatal(err)
	}
	SetDataDir(dir)
	t.Cleanup(func() { SetDataDir("") })
	got := CatalogFor(Current().cats).Opponents(&u, now)
	if len(got) == 0 {
		t.Fatal("no opponents")
	}
	for _, o := range got {
		cpu, _ := ladder.Get(o.PlayerId)
		want := c.Dress(ladder, cpu, &u)
		if o.Costumes != want.Costumes || o.Costumes[0] < 1000 {
			t.Fatalf("opponent %d shows %v, fields %v", o.PlayerId, o.Costumes, want.Costumes)
		}
	}
}

// Deck Builder's matching list: the computer players the player is offered,
// in order, with their lineups; reading it changes nothing.
func TestOpponentsReadTheMatchingList(t *testing.T) {
	c, u := realSave(t)
	now := seasonTime(c)
	if _, ladder, ok := c.Sync(&u, now); ok {
		c.Match(&u.Ext.Pvp, ladder, rand.New(rand.NewPCG(1, 2)))
	}
	before, _ := json.Marshal(u)
	got := CatalogFor(Current().cats).Opponents(&u, now)
	after, _ := json.Marshal(u)
	if string(before) != string(after) {
		t.Fatal("reading the matching list changed the player")
	}
	if len(got) == 0 || len(got) != len(u.Ext.Pvp.Matching) {
		t.Fatalf("opponents %d for matching %v", len(got), u.Ext.Pvp.Matching)
	}
	for i, o := range got {
		if o.PlayerId != u.Ext.Pvp.Matching[i] || o.Costumes[0] == 0 || o.Name == "" {
			t.Fatalf("opponent %d: %+v", i, o)
		}
	}
}
