// Package pvp runs the Arena offline. The other players are computer players
// on a ladder generated per season; their decks are built from playable
// costumes and weapons at levels set relative to the player's own deck. The
// game plays the battles; the server keeps points, grades, battle points,
// logs and weekly results, and simulates computer players attacking the
// player's defense deck.
package pvp

import (
	"log"
	"sort"
	"strconv"
	"sync"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/utils"
)

type Catalog struct {
	cats    *runtime.Catalogs
	seasons []masterdata.EntityMPvpSeason

	grades      map[int32][]masterdata.EntityMPvpGradeGroup // PvpGradeGroupId -> grades by points, ascending
	oneMatch    map[int32][]masterdata.EntityMPvpGradeOneMatchRewardGroup
	oneMatchIds map[int32][]int32 // PvpGradeOneMatchRewardId -> PvpRewardIds
	weeklyGrade map[int32][]int32 // PvpGradeWeeklyRewardGroupId -> PvpRewardIds
	weeklyTiers map[int32][]masterdata.EntityMPvpWeeklyRankRewardRankGroup
	weeklyRank  map[int32][]int32 // PvpWeeklyRankRewardGroupId -> PvpRewardIds
	rewards     map[int32]masterdata.EntityMPvpReward
	groupIds    map[int32]int32 // PvpSeasonGroupingId -> GroupId

	MaxBattlePoint, BattleCost, RefreshCost, RecoverySecond int32

	costumes []costumePick                      // playable costumes the computer players use
	weapons  map[int32][]int32                  // rarity -> playable weapon ids
	pairs    map[int32]int32                    // costume -> its paired weapon
	weapon   map[int32]masterdata.EntityMWeapon // all weapons

	laddersMu sync.Mutex
	ladders   map[int32]*Ladder // by season
}

type costumePick struct {
	CostumeId, CharacterId, Rarity int32
}

var (
	cacheMu sync.Mutex
	cache   = map[*runtime.Catalogs]*Catalog{}
	holder  *runtime.Holder
)

// SetHolder gives the package the server's master data.
func SetHolder(h *runtime.Holder) { holder = h }

// Current is the catalog for the master data in use, or nil before SetHolder.
func Current() *Catalog {
	if holder == nil {
		return nil
	}
	cats := holder.Get()
	cacheMu.Lock()
	defer cacheMu.Unlock()
	if c, ok := cache[cats]; ok {
		return c
	}
	c := load(cats)
	clear(cache) // master data was reloaded: drop the old catalog
	cache[cats] = c
	return c
}

func read[T any](key string) []T {
	rows, err := utils.ReadTable[T](key)
	if err != nil {
		log.Printf("[pvp] read %s: %v", key, err)
	}
	return rows
}

func load(cats *runtime.Catalogs) *Catalog {
	c := &Catalog{
		cats:        cats,
		seasons:     read[masterdata.EntityMPvpSeason]("m_pvp_season"),
		grades:      map[int32][]masterdata.EntityMPvpGradeGroup{},
		oneMatch:    map[int32][]masterdata.EntityMPvpGradeOneMatchRewardGroup{},
		oneMatchIds: map[int32][]int32{},
		weeklyGrade: map[int32][]int32{},
		weeklyTiers: map[int32][]masterdata.EntityMPvpWeeklyRankRewardRankGroup{},
		weeklyRank:  map[int32][]int32{},
		rewards:     map[int32]masterdata.EntityMPvpReward{},
		groupIds:    map[int32]int32{},
		weapons:     map[int32][]int32{},
		pairs:       map[int32]int32{},
		weapon:      map[int32]masterdata.EntityMWeapon{},
		ladders:     map[int32]*Ladder{},
		// The game's own values (m_config), used if a key is missing.
		MaxBattlePoint: 100, BattleCost: 10, RefreshCost: 5, RecoverySecond: 180,
	}
	for _, g := range read[masterdata.EntityMPvpGradeGroup]("m_pvp_grade_group") {
		c.grades[g.PvpGradeGroupId] = append(c.grades[g.PvpGradeGroupId], g)
	}
	for _, l := range c.grades {
		sort.Slice(l, func(i, j int) bool { return l[i].NecessaryPvpPoint < l[j].NecessaryPvpPoint })
	}
	for _, r := range read[masterdata.EntityMPvpGradeOneMatchRewardGroup]("m_pvp_grade_one_match_reward_group") {
		c.oneMatch[r.PvpGradeOneMatchRewardGroupId] = append(c.oneMatch[r.PvpGradeOneMatchRewardGroupId], r)
	}
	for _, r := range read[masterdata.EntityMPvpGradeOneMatchReward]("m_pvp_grade_one_match_reward") {
		c.oneMatchIds[r.PvpGradeOneMatchRewardId] = append(c.oneMatchIds[r.PvpGradeOneMatchRewardId], r.PvpRewardId)
	}
	for _, r := range read[masterdata.EntityMPvpGradeWeeklyRewardGroup]("m_pvp_grade_weekly_reward_group") {
		c.weeklyGrade[r.PvpGradeWeeklyRewardGroupId] = append(c.weeklyGrade[r.PvpGradeWeeklyRewardGroupId], r.PvpRewardId)
	}
	for _, r := range read[masterdata.EntityMPvpWeeklyRankRewardRankGroup]("m_pvp_weekly_rank_reward_rank_group") {
		c.weeklyTiers[r.PvpWeeklyRankRewardRankGroupId] = append(c.weeklyTiers[r.PvpWeeklyRankRewardRankGroupId], r)
	}
	for _, l := range c.weeklyTiers {
		sort.Slice(l, func(i, j int) bool { return l[i].RankLowerLimit < l[j].RankLowerLimit })
	}
	for _, r := range read[masterdata.EntityMPvpWeeklyRankRewardGroup]("m_pvp_weekly_rank_reward_group") {
		c.weeklyRank[r.PvpWeeklyRankRewardGroupId] = append(c.weeklyRank[r.PvpWeeklyRankRewardGroupId], r.PvpRewardId)
	}
	for _, r := range read[masterdata.EntityMPvpReward]("m_pvp_reward") {
		c.rewards[r.PvpRewardId] = r
	}
	for _, g := range read[masterdata.EntityMPvpSeasonGrouping]("m_pvp_season_grouping") {
		if _, ok := c.groupIds[g.PvpSeasonGroupingId]; !ok {
			c.groupIds[g.PvpSeasonGroupingId] = g.GroupId
		}
	}
	for _, kv := range read[masterdata.EntityMConfig]("m_config") {
		v, err := strconv.Atoi(kv.Value)
		if err != nil {
			continue
		}
		switch kv.ConfigKey {
		case "PVP_MAX_BATTLE_POINT":
			c.MaxBattlePoint = int32(v)
		case "PVP_BATTLE_CONSUME_BATTLE_POINT":
			c.BattleCost = int32(v)
		case "PVP_UPDATE_MATCHING_CONSUME_BATTLE_POINT":
			c.RefreshCost = int32(v)
		case "USER_BATTLE_POINT_RECOVERY_SECOND":
			c.RecoverySecond = int32(v)
		}
	}
	if cats.Weapon != nil {
		c.weapon = cats.Weapon.Weapons
	}
	// Computer players use what players could summon: the summon pool's
	// costumes and weapons, each costume with its paired weapon.
	if pool := cats.GachaPool; pool != nil {
		for id, it := range pool.CostumeById {
			c.costumes = append(c.costumes, costumePick{CostumeId: id, CharacterId: it.CharacterId, Rarity: int32(it.RarityType)})
		}
		for id, it := range pool.WeaponById {
			c.weapons[int32(it.RarityType)] = append(c.weapons[int32(it.RarityType)], id)
		}
		for costume, weapon := range pool.CostumeWeaponMap {
			c.pairs[costume] = weapon
		}
	}
	sort.Slice(c.costumes, func(i, j int) bool { return c.costumes[i].CostumeId < c.costumes[j].CostumeId })
	for _, l := range c.weapons {
		sort.Slice(l, func(i, j int) bool { return l[i] < l[j] })
	}
	log.Printf("[pvp] %d seasons, %d costumes and %d weapon rarities for computer players",
		len(c.seasons), len(c.costumes), len(c.weapons))
	return c
}

// Season is the season in force: Bunker's content patcher extends every
// season to 2030, so of those open now, the one that started last.
func (c *Catalog) Season(now int64) (masterdata.EntityMPvpSeason, bool) {
	var best masterdata.EntityMPvpSeason
	found := false
	for _, s := range c.seasons {
		if s.IsInvalid || s.SeasonStartDatetime > now || now >= s.SeasonEndDatetime {
			continue
		}
		if !found || s.SeasonStartDatetime > best.SeasonStartDatetime {
			best, found = s, true
		}
	}
	return best, found
}

func (c *Catalog) seasonById(id int32) (masterdata.EntityMPvpSeason, bool) {
	for _, s := range c.seasons {
		if s.PvpSeasonId == id {
			return s, true
		}
	}
	return masterdata.EntityMPvpSeason{}, false
}

// Grade is the grade for points in a season's grade group.
func (c *Catalog) Grade(season masterdata.EntityMPvpSeason, point int32) masterdata.EntityMPvpGradeGroup {
	var g masterdata.EntityMPvpGradeGroup
	for _, x := range c.grades[season.PvpGradeGroupId] {
		if x.NecessaryPvpPoint <= point {
			g = x
		}
	}
	return g
}

func (c *Catalog) GroupId(season masterdata.EntityMPvpSeason) int32 {
	if g, ok := c.groupIds[season.PvpSeasonGroupingId]; ok {
		return g
	}
	return 1
}

// Reward is one item a PvpReward gives.
type Reward struct {
	PossessionType model.PossessionType
	PossessionId   int32
	Count          int32
}

func (c *Catalog) rewardList(ids []int32) []Reward {
	var out []Reward
	for _, id := range ids {
		if r, ok := c.rewards[id]; ok {
			out = append(out, Reward{model.PossessionType(r.PossessionType), r.PossessionId, r.Count})
		}
	}
	return out
}

// weeklyRankGroup is the weekly rank reward group for a rank.
func (c *Catalog) weeklyRankGroup(season masterdata.EntityMPvpSeason, rank int32) int32 {
	var g int32
	for _, t := range c.weeklyTiers[season.PvpWeeklyRankRewardRankGroupId] {
		if t.RankLowerLimit <= rank {
			g = t.PvpWeeklyRankRewardGroupId
		}
	}
	return g
}
