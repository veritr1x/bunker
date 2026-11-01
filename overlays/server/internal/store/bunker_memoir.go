package store

import (
	"log"
	"math/rand"
	"sort"
)

// A memoir's rank is its sub-status count + 1 (CalculatorMemory.GetMemoryRank),
// and the game opens a memoir's menu (Enhance, Show Story) only when it has a
// sub-status (MemoryThumbnailSetup.CanShowDialogData); with none, a long press
// shows a small preview. So a new memoir has rank − 1 sub-statuses, at least one.
func memoirInitialSubStatusCount(rank int32) int32 {
	return max(rank-1, 1)
}

// RepairMemoirSubStatuses gives memoirs made with no sub-status (before
// memoirInitialSubStatusCount) one. Returns how many it repaired; run at game start.
func (g *PossessionGranter) RepairMemoirSubStatuses(user *UserState, nowMillis int64) int {
	has := make(map[string]bool, len(user.PartsStatusSubs))
	for k := range user.PartsStatusSubs {
		has[k.UserPartsUuid] = true
	}
	uuids := make([]string, 0, len(user.Parts))
	for uuid := range user.Parts {
		if !has[uuid] {
			uuids = append(uuids, uuid)
		}
	}
	sort.Strings(uuids)
	repaired := 0
	for _, uuid := range uuids {
		ref, ok := g.PartsById[user.Parts[uuid].PartsId]
		if !ok {
			continue
		}
		pool := g.PartsSubStatusPool[ref.PartsStatusSubLotteryGroupId]
		if len(pool) == 0 {
			continue
		}
		pick := pool[rand.Intn(len(pool))]
		def, ok := g.PartsSubStatusDefs[pick]
		if !ok {
			continue
		}
		val := def.StatusChangeInitialValue
		if def.StatusFunc != nil {
			val = def.StatusFunc(1)
		}
		user.PartsStatusSubs[PartsStatusSubKey{UserPartsUuid: uuid, StatusIndex: 1}] = PartsStatusSubState{
			UserPartsUuid:           uuid,
			StatusIndex:             1,
			PartsStatusSubLotteryId: pick,
			Level:                   1,
			StatusKindType:          def.StatusKindType,
			StatusCalculationType:   def.StatusCalculationType,
			StatusChangeValue:       val,
			LatestVersion:           nowMillis,
		}
		repaired++
	}
	if repaired > 0 {
		log.Printf("[GrantParts] user %d: %d memoirs without a sub-status given one", user.UserId, repaired)
	}
	return repaired
}
