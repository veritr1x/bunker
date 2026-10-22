package service

import (
	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/gacha"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// eventSummonGachas is an event's summon as the client lists it: one Gacha
// per level (ids base, base+1, ...), grouped by GachaBoxGroupId, all with the
// player's level as CurrentBoxNumber; each shows its level's main prizes, and
// the current one offers Level Up (Prize Replenishment on the last level)
// once it is done.
func eventSummonGachas(entry store.GachaCatalogEntry, box masterdata.EventSummon, bs *store.GachaBannerState, user store.UserState) []*pb.Gacha {
	var state store.GachaBannerState
	if bs != nil {
		state = *bs
	}
	current := gacha.EventLevel(state)
	out := make([]*pb.Gacha, 0, len(box.Levels))
	for i, level := range box.Levels {
		n := int32(i + 1)
		g := toProtoGachaFor(entry, bs, user)
		g.GachaId = box.Base + int32(i)
		mode, ok := g.GachaMode.(*pb.Gacha_GachaModeBoxComposition)
		if !ok {
			return []*pb.Gacha{toProtoGachaFor(entry, bs, user)}
		}
		m := mode.GachaModeBoxComposition
		m.GachaBoxGroupId = box.Base
		m.BoxNumber = n
		m.CurrentBoxNumber = current
		m.GachaAssetName = box.Assets[i]
		m.IsResettableByDrawingAllTargets = true
		m.IsAlreadyDrawn = n == current && len(state.BoxDrewCounts) > 0
		m.IsCurrentBoxResettable = n == current && gacha.EventCanAdvance(state, box)
		m.IsHideMultipleDrawButton = false
		m.PromotionGachaOddsItem = nil
		for j, p := range level.Items {
			if !p.Main {
				continue
			}
			drew := int32(0)
			switch {
			case n < current:
				drew = p.Stock // a level left behind is done
			case n == current:
				drew = p.Stock - gacha.EventPrizeLeft(state, j, p)
			}
			m.PromotionGachaOddsItem = append(m.PromotionGachaOddsItem, &pb.GachaOddsItem{
				GachaItem:        &pb.GachaItem{PossessionType: p.Type, PossessionId: p.Id, Count: max(p.Count, 1), PromotionOrder: int32(len(m.PromotionGachaOddsItem) + 1)},
				GachaItemBonus:   &pb.GachaItem{},
				MaxDrawableCount: p.Stock,
				DrewCount:        drew,
				IsTarget:         p.Target,
			})
		}
		out = append(out, g)
	}
	return out
}
