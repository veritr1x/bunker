package service

import (
	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Exploration (the Shooting and Flying Mama minigames) paid stamina and
// items by the grade of the score. The game data has the grades (six, from
// m_explore_grade_score), the number of reward draws (RewardLotteryCount: 1,
// or 11 on hard) and the ticket costs, but not what a draw gives, so these
// are chosen here: the better the grade, the more stamina and the larger the
// items. A draw is gold (25%) or a costume or weapon experience material,
// small or medium.

var (
	exploreSmallMaterials  = []int32{100001, 200001} // costume and weapon experience, small
	exploreMediumMaterials = []int32{100002, 200002} // medium
)

// exploreGradeRank is the grade of score from 0 (lowest) to the best (5).
func exploreGradeRank(catalog *masterdata.ExploreCatalog, exploreId, score int32) int {
	rows := catalog.GradeScores[exploreId] // best grade first
	for i, r := range rows {
		if score >= r.NecessaryScore {
			return len(rows) - 1 - i
		}
	}
	return 0
}

// exploreStamina is the stamina a finish adds.
func exploreStamina(rank int) int32 { return 5 + 5*int32(rank) }

// exploreDraws makes the run's reward draws and grants them; intn is rand.Intn.
func exploreDraws(user *store.UserState, goldItemId int32, rank int, draws int32, intn func(int) int) []*pb.ExploreReward {
	type key struct{ kind, id int32 }
	totals := map[key]int32{}
	var order []key
	add := func(k key, n int32) {
		if _, ok := totals[k]; !ok {
			order = append(order, k)
		}
		totals[k] += n
	}
	for range draws {
		if intn(100) < 25 {
			add(key{int32(model.PossessionTypeConsumableItem), goldItemId}, 500*int32(rank+1))
			continue
		}
		pool := exploreSmallMaterials
		if intn(100) < 10+12*rank {
			pool = exploreMediumMaterials
		}
		add(key{int32(model.PossessionTypeMaterial), pool[intn(len(pool))]}, 1)
	}
	out := make([]*pb.ExploreReward, 0, len(order))
	for _, k := range order {
		store.GrantPossession(user, model.PossessionType(k.kind), k.id, totals[k])
		out = append(out, &pb.ExploreReward{PossessionType: k.kind, PossessionId: k.id, Count: totals[k]})
	}
	return out
}
