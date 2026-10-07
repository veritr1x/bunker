package pvp

import (
	"fmt"
	"math"
	"math/rand/v2"
	"sort"

	"lunar-tear/server/internal/model"
)

const (
	ladderSize = 5000
	// Computer player ids start here, far above real player ids.
	CpuIdBase int64 = 9_000_000_000
	// topPoint is the most points a computer player has (grade 25 needs 46000).
	topPoint = 52000
)

// CPU is a computer player on the ladder.
type CPU struct {
	PlayerId int64
	Name     string
	Point    int32
	Costumes [3]int32
	Weapons  [3]int32
}

// Ladder is a season's computer players. It is generated from the season id,
// so it is the same each time the server starts.
type Ladder struct {
	cpus   []CPU
	points []int32 // all points, descending
	order  []int   // cpus indexes by points, descending
}

func IsCPU(playerId int64) bool { return playerId > CpuIdBase && playerId <= CpuIdBase+ladderSize }

func (c *Catalog) Ladder(seasonId int32) *Ladder {
	c.laddersMu.Lock()
	defer c.laddersMu.Unlock()
	if l, ok := c.ladders[seasonId]; ok {
		return l
	}
	l := &Ladder{cpus: make([]CPU, ladderSize), points: make([]int32, ladderSize)}
	for i := range l.cpus {
		r := rand.New(rand.NewPCG(uint64(seasonId), uint64(i)))
		cpu := CPU{
			PlayerId: CpuIdBase + int64(i) + 1,
			Name:     cpuName(r),
			// Most players sit in the lower grades, a few near the top.
			Point: int32(topPoint * math.Pow(r.Float64(), 2.5)),
		}
		c.pickDeck(r, &cpu)
		l.cpus[i] = cpu
		l.points[i] = cpu.Point
	}
	sort.Slice(l.points, func(i, j int) bool { return l.points[i] > l.points[j] })
	l.order = make([]int, len(l.cpus))
	for i := range l.order {
		l.order[i] = i
	}
	sort.SliceStable(l.order, func(a, b int) bool { return l.cpus[l.order[a]].Point > l.cpus[l.order[b]].Point })
	c.ladders[seasonId] = l
	return l
}

func (l *Ladder) Get(playerId int64) (CPU, bool) {
	if !IsCPU(playerId) {
		return CPU{}, false
	}
	return l.cpus[playerId-CpuIdBase-1], true
}

func (l *Ladder) Size() int { return len(l.cpus) }

// above counts the computer players with more points.
func (l *Ladder) above(point int32) int32 {
	return int32(sort.Search(len(l.points), func(i int) bool { return l.points[i] <= point }))
}

// Rank is the player's rank with these points.
func (l *Ladder) Rank(point int32) int32 { return l.above(point) + 1 }

// CPURank is a computer player's rank with the player on the ladder too.
func (l *Ladder) CPURank(cpu CPU, playerPoint int32) int32 {
	rank := l.above(cpu.Point) + 1
	if playerPoint > cpu.Point {
		rank++
	}
	return rank
}

// Ranked lists the ladder from a rank (1-based) with the player in place:
// the player is ranked above computer players with equal points.
func (l *Ladder) Ranked(from, count int, playerPoint int32) []RankEntry {
	order := l.order
	playerAt := int(l.above(playerPoint)) // index in the combined list
	var out []RankEntry
	for pos := from - 1; pos < len(order)+1 && len(out) < count; pos++ {
		if pos < 0 {
			continue
		}
		switch {
		case pos == playerAt:
			out = append(out, RankEntry{Rank: int32(pos + 1), Player: true})
		case pos < playerAt:
			out = append(out, RankEntry{Rank: int32(pos + 1), CPU: l.cpus[order[pos]]})
		default:
			out = append(out, RankEntry{Rank: int32(pos + 1), CPU: l.cpus[order[pos-1]]})
		}
	}
	return out
}

type RankEntry struct {
	Rank   int32
	Player bool
	CPU    CPU
}

// Near finds the computer player with points closest to target, skipping some.
func (l *Ladder) Near(target int32, skip map[int64]bool, r *rand.Rand) (CPU, bool) {
	best, bestDiff := -1, int32(math.MaxInt32)
	// Start at a random index so equal distances do not always pick the same player.
	start := r.IntN(len(l.cpus))
	for k := range l.cpus {
		i := (start + k) % len(l.cpus)
		if skip[l.cpus[i].PlayerId] {
			continue
		}
		d := l.cpus[i].Point - target
		if d < 0 {
			d = -d
		}
		if d < bestDiff {
			best, bestDiff = i, d
		}
	}
	if best < 0 {
		return CPU{}, false
	}
	return l.cpus[best], true
}

// pickDeck gives a computer player three characters, more often ★4 the
// higher their points, each costume with its paired weapon.
func (c *Catalog) pickDeck(r *rand.Rand, cpu *CPU) {
	if len(c.costumes) == 0 {
		return
	}
	fourStar := 0.25 + 0.65*float64(cpu.Point)/topPoint
	used := map[int32]bool{}
	for slot := 0; slot < 3; slot++ {
		want := model.RaritySRare
		if r.Float64() < fourStar {
			want = model.RaritySSRare
		}
		var pick costumePick
		for try := 0; try < 50; try++ {
			p := c.costumes[r.IntN(len(c.costumes))]
			if used[p.CharacterId] {
				continue
			}
			pick = p
			if p.Rarity == int32(want) {
				break
			}
		}
		if pick.CostumeId == 0 {
			continue
		}
		used[pick.CharacterId] = true
		cpu.Costumes[slot] = pick.CostumeId
		weapon, ok := c.pairs[pick.CostumeId]
		if !ok {
			if list := c.weapons[pick.Rarity]; len(list) > 0 {
				weapon = list[r.IntN(len(list))]
			}
		}
		cpu.Weapons[slot] = weapon
	}
}

var (
	nameFirst = []string{"Ashen", "Silent", "Crimson", "Hollow", "Pale", "Lost", "Quiet", "Iron", "Gentle", "Broken",
		"Wandering", "Gilded", "Faded", "Bright", "Lonely", "Distant", "Velvet", "Hidden", "Frozen", "Golden",
		"Rusted", "Sleepy", "Little", "Tender", "Wild", "Shining", "Last", "Bitter", "Sweet", "Fallen"}
	nameSecond = []string{"Cage", "Lantern", "Feather", "Raven", "Bell", "Rose", "Thorn", "Moon", "Ghost", "Lily",
		"Doll", "Echo", "Ember", "Petal", "Wing", "Key", "Mirror", "Story", "Song", "Tower",
		"Garden", "Candle", "Ribbon", "Shadow", "Dream", "Star", "Mask", "Sword", "Clock", "Book"}
)

func cpuName(r *rand.Rand) string {
	name := nameFirst[r.IntN(len(nameFirst))] + nameSecond[r.IntN(len(nameSecond))]
	if r.IntN(3) > 0 {
		name += fmt.Sprintf("%d", r.IntN(999)+1)
	}
	return name
}
