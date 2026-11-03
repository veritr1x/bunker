package missions

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/store"
)

// IDs alone are not portable between Global and Japanese master data. The
// condition identifies the counter and its filters; the target is deliberately
// excluded, since the engine reads each mission's own target from master data.
type ruleCondition [4]int32

func condition(m masterdata.EntityMMission) ruleCondition {
	return ruleCondition{m.MissionClearConditionType, m.MissionClearConditionGroupId,
		m.MissionClearConditionOptionGroupId, m.MissionClearConditionOptionDetailGroupId}
}

type ruleSet struct {
	byId        map[int32][]Rule
	byCondition map[ruleCondition]Rule
	ambiguous   map[ruleCondition]bool
	legacy      map[int32]Rule
}

func loadRules() (*ruleSet, error) {
	var base, regional []Rule
	if err := json.Unmarshal(rulesJSON, &base); err != nil {
		return nil, err
	}
	if err := json.Unmarshal(regionalRulesJSON, &regional); err != nil {
		return nil, err
	}
	return newRuleSet(base, regional)
}

func newRuleSet(base, regional []Rule) (*ruleSet, error) {
	s := &ruleSet{byId: map[int32][]Rule{}, byCondition: map[ruleCondition]Rule{},
		ambiguous: map[ruleCondition]bool{}, legacy: map[int32]Rule{}}
	for _, r := range base {
		s.legacy[r.MissionId] = r
	}
	for _, rules := range [][]Rule{base, regional} {
		for _, r := range rules {
			if r.Condition[0] == 0 || r.Kind == "" {
				return nil, fmt.Errorf("mission rule %d has no condition or kind", r.MissionId)
			}
			for _, existing := range s.byId[r.MissionId] {
				if existing.Condition == r.Condition {
					return nil, fmt.Errorf("mission rule %d repeats condition %v", r.MissionId, r.Condition)
				}
			}
			s.byId[r.MissionId] = append(s.byId[r.MissionId], r)
			if previous, ok := s.byCondition[r.Condition]; ok && ruleRevision(previous) != ruleRevision(r) {
				s.ambiguous[r.Condition] = true
			}
			s.byCondition[r.Condition] = r
		}
	}
	return s, nil
}

func (s *ruleSet) find(m masterdata.EntityMMission) (Rule, bool) {
	want := condition(m)
	for _, r := range s.byId[m.MissionId] {
		if r.Condition == want {
			return r, true
		}
	}
	// Some JP IDs refer to counters assigned to other Global IDs. Reuse only
	// when every known rule for that exact condition has identical filters.
	// A mission with no verified rule still stays unsupported unless it has
	// an explicit regional definition; its name may contain extra conditions.
	if _, known := s.legacy[m.MissionId]; !known {
		return Rule{}, false
	}
	if r, ok := s.byCondition[want]; ok && !s.ambiguous[want] {
		r.MissionId = m.MissionId
		return r, true
	}
	return Rule{}, false
}

func ruleRevision(r Rule) string {
	r.MissionId = 0
	r.Condition = ruleCondition{}
	b, _ := json.Marshal(r)
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:])
}

func (s *ruleSet) change(id int32, actual Rule) string {
	if ruleRevision(s.legacy[id]) == ruleRevision(actual) {
		return ""
	}
	return ruleRevision(actual)
}

// Reconcile before tracking AND before paying: the reward handler runs before
// the tracking interceptor, so an old false completion must not be claimable
// on the first request after updating. Already paid rewards stay received.
// Save only deviations from the old ID-only rules, including across imports
// of another region's master data; ordinary saves do not need 6,000 hashes.
func (cat *Catalog) reconcileRules(u *store.UserState, now int64) {
	ids := map[int32]bool{}
	for id := range cat.ruleChanges {
		ids[id] = true
	}
	for id := range u.Ext.MissionRuleRevisions {
		ids[id] = true
	}
	for id := range ids {
		if cat.ById[id] == nil {
			continue
		}
		current := cat.ruleChanges[id]
		if u.Ext.MissionRuleRevisions[id] == current {
			continue
		}
		if rec, ok := u.Missions[id]; ok && rec.MissionProgressStatusType != StatusRewardReceived {
			u.Missions[id] = store.UserMissionState{MissionId: id, StartDatetime: now,
				MissionProgressStatusType: StatusInProgress, LatestVersion: now}
		}
		if current == "" {
			delete(u.Ext.MissionRuleRevisions, id)
		} else {
			if u.Ext.MissionRuleRevisions == nil {
				u.Ext.MissionRuleRevisions = map[int32]string{}
			}
			u.Ext.MissionRuleRevisions[id] = current
		}
	}
}
