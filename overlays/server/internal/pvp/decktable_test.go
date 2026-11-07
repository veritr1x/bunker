package pvp

import (
	"encoding/json"
	"math/rand/v2"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"lunar-tear/server/internal/runtime"
)

// A table of n decks with qualities from 1 down to 0.
func testTable(n int) *DeckTable {
	t := &DeckTable{PowerToQuality: [][2]float64{{100000, 0.2}, {300000, 0.5}, {400000, 0.9}}}
	for i := 0; i < n; i++ {
		q := 1 - float64(i)/float64(n-1)
		t.Decks = append(t.Decks, DeckLoadout{Quality: q, Power: int32(100000 + 300000*q), Characters: []LoadoutCharacter{
			{Costume: int32(1000 + i), MainWeapon: 7, Subs: []int32{8, 9}, Companion: 3, Thought: 5,
				Parts: []LoadoutPart{{Id: 404, Main: 28, Subs: [][3]int32{{3, 1, 140}}}}},
		}})
	}
	return t
}

func TestTop100AreMeta(t *testing.T) {
	table := testTable(500)
	r := rand.New(rand.NewPCG(1, 2))
	cut := table.Decks[len(table.Decks)/50].Quality // the top 2%
	for rank := 1; rank <= 100; rank++ {
		if d := table.Pick(rank, 5000, 0.1, r); d.Quality < cut {
			t.Fatalf("rank %d got quality %.3f, below the top 2%% (%.3f)", rank, d.Quality, cut)
		}
	}
}

func TestQualityRisesWithRank(t *testing.T) {
	table := testTable(500)
	r := rand.New(rand.NewPCG(3, 4))
	var means []float64
	for decile := 0; decile < 10; decile++ {
		sum := 0.0
		for i := 0; i < 50; i++ {
			rank := 5000 - (decile*500 + i*10)
			sum += table.Pick(rank, 5000, 0.3, r).Quality
		}
		means = append(means, sum/50)
	}
	for i := 1; i < len(means); i++ {
		if means[i]+0.02 < means[i-1] {
			t.Fatalf("quality falls toward rank 1: %v", means)
		}
	}
}

func TestScalesToPlayer(t *testing.T) {
	table := testTable(500)
	mid := func(q float64) float64 {
		r := rand.New(rand.NewPCG(5, 6))
		sum := 0.0
		for i := 0; i < 100; i++ {
			sum += table.Pick(3500+i, 5000, q, r).Quality
		}
		return sum / 100
	}
	if weak, strong := mid(0.1), mid(0.8); strong <= weak+0.2 {
		t.Fatalf("mid-ladder quality %.2f (weak player) vs %.2f (strong player)", weak, strong)
	}
}

func TestPlayerQuality(t *testing.T) {
	dir := t.TempDir()
	table := testTable(10)
	if q := PlayerQuality(dir, 1, 300000, table); q != 0.5 {
		t.Fatalf("from Force: %.3f, want 0.5", q)
	}
	if q := PlayerQuality(dir, 1, 350000, table); q < 0.69 || q > 0.71 {
		t.Fatalf("between curve points: %.3f, want 0.7", q)
	}
	b, _ := json.Marshal(map[string]any{"1": map[string]any{"attack": 0.42, "defense": 0.66, "power": 1}})
	os.WriteFile(filepath.Join(dir, playerFile), b, 0o644)
	if q := PlayerQuality(dir, 1, 300000, table); q != 0.42 {
		t.Fatalf("scored player: %.3f, want their attack score 0.42", q)
	}
}

func TestNoTableUnchanged(t *testing.T) {
	c := &Catalog{cats: &runtime.Catalogs{}}
	cpu := CPU{PlayerId: CpuIdBase + 7, Costumes: [3]int32{10, 20, 30}, Weapons: [3]int32{1, 2, 3}}
	if got := c.dress(nil, nil, cpu, 0.5); !reflect.DeepEqual(got, cpu) {
		t.Fatalf("dressed without a table: %+v", got)
	}
	before := c.Deck(cpu, Profile{}, 1)
	if len(before) != 3 || before[0].Companion.CompanionId != 0 || len(before[0].Parts) != 0 {
		t.Fatalf("plain deck: %+v", before[0])
	}
}

func TestDeckCarriesFullLoadout(t *testing.T) {
	c := &Catalog{cats: &runtime.Catalogs{}}
	l := &Ladder{cpus: make([]CPU, 50)}
	cpu := CPU{PlayerId: CpuIdBase + 1, Costumes: [3]int32{10, 20, 30}}
	dressed := c.dress(testTable(20), l, cpu, 0.5)
	if dressed.Loadout == nil || dressed.Costumes[0] == 10 {
		t.Fatalf("not dressed: %+v", dressed)
	}
	if again := c.dress(testTable(20), l, cpu, 0.5); !reflect.DeepEqual(again, dressed) {
		t.Fatal("the same computer player was dressed differently (list and battle must match)")
	}
	deck := c.Deck(dressed, Profile{}, 1)
	ch := deck[0]
	if ch.Costume.CostumeId != dressed.Costumes[0] || ch.Companion.CompanionId != 3 || len(ch.SubWeapon) != 2 || ch.Thought.ThoughtId != 5 {
		t.Fatalf("deck character: %+v", ch)
	}
	if len(ch.Parts) != 1 || ch.Parts[0].PartsMainStatusId != 28 || ch.Parts[0].SubPartsStatus[0].StatusChangeValue != 140 {
		t.Fatalf("memoirs: %+v", ch.Parts)
	}
}
