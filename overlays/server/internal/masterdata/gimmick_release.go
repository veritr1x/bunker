package masterdata

import (
	"log"
	"math/bits"

	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// EvaluateConditionFunctionType / EvaluateType values a gimmick's
// ReleaseEvaluateConditionId uses (client enums of the same names).
const (
	evalFuncRecursion            = 1
	evalFuncQuestClear           = 4
	evalFuncOtherGimmickBitCount = 10

	evalTypeAnd       = 1
	evalTypeOr        = 2
	evalTypeGe        = 3
	evalTypeIdContain = 4
)

// gimmickCondition is a parsed m_evaluate_condition tree.
type gimmickCondition struct {
	id       int32
	funcType int32
	evalType int32
	values   []int64 // by GroupIndex
	subs     []*gimmickCondition
}

// loadGimmickReleaseConditions parses each gimmick's ReleaseEvaluateConditionId.
// In 3.7.1 these are the 28 Lost Archives (type 10) gated on RECURSION OR of
// OTHER_GIMMICK_BIT_COUNT GE: finding one of four other Lost Archives.
func loadGimmickReleaseConditions() map[int32]*gimmickCondition {
	out := map[int32]*gimmickCondition{}
	gimmicks, ok := readGimmickTable[EntityMGimmick]("m_gimmick", "release conditions")
	if !ok {
		return out
	}
	conditions, ok := readGimmickTable[EntityMEvaluateCondition]("m_evaluate_condition", "release conditions")
	if !ok {
		return out
	}
	valueRows, ok := readGimmickTable[EntityMEvaluateConditionValueGroup]("m_evaluate_condition_value_group", "release conditions")
	if !ok {
		return out
	}
	condById := make(map[int32]EntityMEvaluateCondition, len(conditions))
	for _, c := range conditions {
		condById[c.EvaluateConditionId] = c
	}
	valuesByGroup := make(map[int32]map[int32]int64)
	for _, v := range valueRows {
		if valuesByGroup[v.EvaluateConditionValueGroupId] == nil {
			valuesByGroup[v.EvaluateConditionValueGroupId] = map[int32]int64{}
		}
		valuesByGroup[v.EvaluateConditionValueGroupId][v.GroupIndex] = v.Value
	}
	var parse func(id int32, depth int) *gimmickCondition
	parse = func(id int32, depth int) *gimmickCondition {
		c, ok := condById[id]
		if !ok || depth > 8 {
			return nil
		}
		gc := &gimmickCondition{id: id, funcType: c.EvaluateConditionFunctionType, evalType: c.EvaluateConditionEvaluateType}
		byIndex := valuesByGroup[c.EvaluateConditionValueGroupId]
		for i := int32(1); i <= int32(len(byIndex)); i++ {
			gc.values = append(gc.values, byIndex[i])
		}
		if gc.funcType == evalFuncRecursion {
			for _, sub := range gc.values {
				if s := parse(int32(sub), depth+1); s != nil {
					gc.subs = append(gc.subs, s)
				}
			}
		}
		return gc
	}
	for _, g := range gimmicks {
		if g.ReleaseEvaluateConditionId == 0 {
			continue
		}
		if gc := parse(g.ReleaseEvaluateConditionId, 0); gc != nil {
			out[g.GimmickId] = gc
		}
	}
	return out
}

func (gc *gimmickCondition) met(user store.UserState) bool {
	v := gc.values
	switch {
	case gc.funcType == evalFuncRecursion && gc.evalType == evalTypeAnd:
		for _, s := range gc.subs {
			if !s.met(user) {
				return false
			}
		}
		return len(gc.subs) > 0
	case gc.funcType == evalFuncRecursion && gc.evalType == evalTypeOr:
		for _, s := range gc.subs {
			if s.met(user) {
				return true
			}
		}
		return false
	case gc.funcType == evalFuncOtherGimmickBitCount && gc.evalType == evalTypeGe && len(v) >= 5:
		// Values: schedule, sequence, gimmick, ornament index, bit count.
		p := user.Gimmick.OrnamentProgress[store.GimmickOrnamentKey{
			GimmickSequenceScheduleId: int32(v[0]),
			GimmickSequenceId:         int32(v[1]),
			GimmickId:                 int32(v[2]),
			GimmickOrnamentIndex:      int32(v[3]),
		}]
		return int64(bits.OnesCount32(uint32(p.ProgressValueBit))) >= v[4]
	case gc.funcType == evalFuncQuestClear && gc.evalType == evalTypeIdContain && len(v) >= 1:
		q, ok := user.Quests[int32(v[0])]
		return ok && q.QuestStateType == model.UserQuestStateTypeCleared
	default:
		log.Printf("[gimmick] evaluate condition %d (func %d, type %d) not handled, treated as met", gc.id, gc.funcType, gc.evalType)
		return true
	}
}

// GimmickReleased reports whether a gimmick's own release condition holds;
// gimmicks without one are always released.
func (c *GimmickCatalog) GimmickReleased(user store.UserState, gimmickId int32) bool {
	gc, ok := c.releaseConditions[gimmickId]
	return !ok || gc.met(user)
}
