package pvp

// The computer players' decks from Pod Programs › Deck Builder
// (bunker_arena_decks.json beside the save, written by deckbuilder/ladder.py):
// real lineups with full loadouts, each rated by quality (its win rate against
// the meta decks). The top of the ladder always fields the strongest decks;
// below it, quality follows a curve from the player's own deck quality up to
// the top, so opponents scale to deck strength, not only Force. Without the
// file, computer players are as before.

import (
	"encoding/json"
	"math"
	"math/rand/v2"
	"os"
	"path/filepath"
	"sort"
	"sync"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

const (
	deckFile   = "bunker_arena_decks.json"
	playerFile = "bunker_arena_players.json"
	metaRanks  = 100  // ranks that always field the strongest decks
	metaShare  = 0.02 // the strongest decks: this share of the table
	curveGamma = 2.0
	jitter     = 0.03
)

type LoadoutPart struct {
	Id   int32      `json:"id"`
	Main int32      `json:"main"`
	Subs [][3]int32 `json:"subs"` // kind, calculation, value
}

type LoadoutCharacter struct {
	Costume    int32         `json:"costume"`
	MainWeapon int32         `json:"main_weapon"`
	Subs       []int32       `json:"subs"`
	Companion  int32         `json:"companion"`
	Parts      []LoadoutPart `json:"parts"`
	Thought    int32         `json:"thought"`
	Karma      []int32       `json:"karma"`
	Awaken     int32         `json:"awaken"`
	Board      bool          `json:"board"`
}

type DeckLoadout struct {
	Quality    float64            `json:"quality"`
	Power      int32              `json:"power"`
	Characters []LoadoutCharacter `json:"characters"`
}

type DeckTable struct {
	Decks          []DeckLoadout `json:"decks"` // strongest first
	PowerToQuality [][2]float64  `json:"power_to_quality"`
}

var (
	dataDir   string
	tableMu   sync.Mutex
	tableAt   int64
	tableData *DeckTable
)

// SetDataDir is where the save and Deck Builder's files are.
func SetDataDir(dir string) { dataDir = dir }

// LoadDeckTable reads a deck table, strongest deck first.
func LoadDeckTable(path string) (*DeckTable, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var t DeckTable
	if err := json.Unmarshal(b, &t); err != nil {
		return nil, err
	}
	sort.SliceStable(t.Decks, func(i, j int) bool { return t.Decks[i].Quality > t.Decks[j].Quality })
	return &t, nil
}

// currentTable is the table beside the save, read again when it changes; nil without one.
func currentTable() *DeckTable {
	if dataDir == "" {
		return nil
	}
	path := filepath.Join(dataDir, deckFile)
	st, err := os.Stat(path)
	tableMu.Lock()
	defer tableMu.Unlock()
	if err != nil {
		tableData, tableAt = nil, 0
		return nil
	}
	if st.ModTime().UnixNano() != tableAt {
		t, err := LoadDeckTable(path)
		if err != nil || len(t.Decks) == 0 {
			t = nil
		}
		tableData, tableAt = t, st.ModTime().UnixNano()
	}
	return tableData
}

// Pick is the deck a computer player at rank (1 = top) of a ladder of
// ladderSize fields against a player whose decks rate playerQuality.
func (t *DeckTable) Pick(rank, ladderSize int, playerQuality float64, r *rand.Rand) DeckLoadout {
	n := len(t.Decks)
	if rank <= metaRanks {
		top := max(1, int(math.Ceil(float64(n)*metaShare)))
		return t.Decks[r.IntN(top)]
	}
	qTop := t.Decks[0].Quality
	share := 1 - float64(rank)/float64(max(ladderSize, 1))
	target := playerQuality + (qTop-playerQuality)*math.Pow(math.Max(share, 0), curveGamma)
	target += (r.Float64()*2 - 1) * jitter
	// decks are strongest first: the first one at or below the target
	i := sort.Search(n, func(i int) bool { return t.Decks[i].Quality <= target })
	if i == n {
		i = n - 1
	}
	if i > 0 && math.Abs(t.Decks[i-1].Quality-target) < math.Abs(t.Decks[i].Quality-target) {
		i--
	}
	return t.Decks[i]
}

// PlayerQuality is how strong the player's Arena decks are: Deck Builder's
// score for them, else their Force read through the table's curve.
func PlayerQuality(dir string, userId int64, power int32, t *DeckTable) float64 {
	if b, err := os.ReadFile(filepath.Join(dir, playerFile)); err == nil {
		var scores map[string]struct {
			Attack float64 `json:"attack"`
		}
		if json.Unmarshal(b, &scores) == nil {
			if s, ok := scores[itoa(userId)]; ok {
				return s.Attack
			}
		}
	}
	c := t.PowerToQuality
	if len(c) == 0 {
		return 0
	}
	p := float64(power)
	if p <= c[0][0] {
		return c[0][1]
	}
	for i := 1; i < len(c); i++ {
		if p <= c[i][0] {
			f := (p - c[i-1][0]) / (c[i][0] - c[i-1][0])
			return c[i-1][1] + f*(c[i][1]-c[i-1][1])
		}
	}
	return c[len(c)-1][1]
}

func itoa(v int64) string {
	b, _ := json.Marshal(v)
	return string(b)
}

// Dress gives a computer player its deck from the table for this player; the
// same computer player gets the same deck while the player's quality holds,
// so the matching list and the battle agree. Without a table it is unchanged.
func (c *Catalog) Dress(l *Ladder, cpu CPU, u *store.UserState) CPU {
	t := currentTable()
	if t == nil {
		return cpu
	}
	p := c.ProfileOf(u, store.DeckKey{DeckType: model.DeckTypePvp, UserDeckNumber: max(1, u.Ext.Pvp.DefenseDeckNumber)})
	return c.dress(t, l, cpu, PlayerQuality(dataDir, u.UserId, DeckPower(p, 1), t))
}

func (c *Catalog) dress(t *DeckTable, l *Ladder, cpu CPU, quality float64) CPU {
	if t == nil || l == nil {
		return cpu
	}
	r := rand.New(rand.NewPCG(uint64(cpu.PlayerId), uint64(math.Round(quality*100))))
	rank := l.CPURank(cpu, 0)
	d := t.Pick(int(rank), max(l.Size(), 1), quality, r)
	out := cpu
	out.Loadout = &d
	out.Costumes, out.Weapons = [3]int32{}, [3]int32{}
	for i, ch := range d.Characters {
		if i < 3 {
			out.Costumes[i], out.Weapons[i] = ch.Costume, ch.MainWeapon
		}
	}
	return out
}
