package missions

import (
	"math"
	"math/bits"
	"strings"
	"time"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/userdata"
)

// trackVersion is stored in ExtState.MissionsVersion once a save's missions
// have been backfilled from what the player already did.
const trackVersion = 1

// MissionUnlockConditionType values from the game client.
const (
	unlockQuestClear     = 2
	unlockMissionClearBy = 3
)

// Kinds whose value is read from the save each time, not counted.
var stateKinds = map[string]bool{
	"user_level": true, "costume_level": true, "weapon_level": true, "costume_skill_level": true,
	"weapon_skill_level": true, "weapon_ability_level": true, "favorite_character": true,
	"board_panel": true, "big_hunt_score": true, "max_deck_power": true,
}

// counts holds what one request added, per kind; a mission's own filter picks
// the entries it counts.
type counts struct {
	clears    []questClear
	amount    map[string]int64
	byWeapon  map[string]map[int32]int64 // kind -> weapon id -> amount
	byCostume map[string]map[int32]int64
	byChar    map[string]map[int32]int64
	gacha     map[string]int64 // "" all, "daily", "chapter"
}

type questClear struct {
	questId  int32
	count    int64
	skipped  bool
	costumes []int32
}

func newCounts() *counts {
	return &counts{amount: map[string]int64{}, byWeapon: map[string]map[int32]int64{},
		byCostume: map[string]map[int32]int64{}, byChar: map[string]map[int32]int64{}, gacha: map[string]int64{}}
}

func add[K comparable](m map[string]map[K]int64, kind string, key K, n int64) {
	if n <= 0 {
		return
	}
	if m[kind] == nil {
		m[kind] = map[K]int64{}
	}
	m[kind][key] += n
}

// GachaLabel tells the engine a banner's label (model.GachaLabel*).
var GachaLabel func(gachaId int32) int32

func startOfDay(now int64) int64 {
	t := time.UnixMilli(now).UTC()
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, time.UTC).UnixMilli()
}

// deckCostumes lists the costumes in a quest deck.
func deckCostumes(u *store.UserState, number int32) []int32 {
	var out []int32
	for _, dt := range []model.DeckType{model.DeckTypeQuest, model.DeckTypeRestrictedQuest, model.DeckTypeRestrictedLimitContentQuest} {
		d, ok := u.Decks[store.DeckKey{DeckType: dt, UserDeckNumber: number}]
		if !ok {
			continue
		}
		for _, id := range []string{d.UserDeckCharacterUuid01, d.UserDeckCharacterUuid02, d.UserDeckCharacterUuid03} {
			if dc, ok := u.DeckCharacters[id]; ok {
				if co, ok := u.Costumes[dc.UserCostumeUuid]; ok {
					out = append(out, co.CostumeId)
				}
			}
		}
		break
	}
	return out
}

// collect works out what a request did from the save before and after it.
func collect(before, after *store.UserState, method string, req any) *counts {
	c := newCounts()
	name := method[strings.LastIndex(method, "/")+1:]
	skipped := strings.Contains(name, "Skip")
	deck := int32(0)
	switch r := req.(type) {
	case *pb.SkipQuestRequest:
		deck = r.UserDeckNumber
	case *pb.SkipQuestBulkRequest:
		deck = r.UserDeckNumber
	case *pb.FinishMainQuestRequest:
		if r.IsRetired {
			c.amount["battle_retire"]++
		}
		if r.IsAnnihilated {
			c.amount["battle_annihilated"]++
		}
	case *pb.FinishEventQuestRequest:
		if r.IsRetired {
			c.amount["battle_retire"]++
		}
		if r.IsAnnihilated {
			c.amount["battle_annihilated"]++
		}
	case *pb.UpdateMissionProgressRequest:
		if v := r.CageMeasurableValues; v != nil {
			c.amount["cage_walk"] += int64(v.RunningDistanceMeters)
			c.amount["mama_tap"] += int64(v.MamaTappedCount)
		}
		if v := r.PictureBookMeasurableValues; v != nil {
			c.amount["defeat_wizard"] += int64(v.DefeatWizardCount)
		}
	}
	for id, q := range after.Quests {
		n := int64(q.ClearCount) - int64(before.Quests[id].ClearCount)
		if n <= 0 {
			continue
		}
		number := deck
		if number == 0 {
			number = q.UserDeckNumber
		}
		c.clears = append(c.clears, questClear{questId: id, count: n, skipped: skipped, costumes: deckCostumes(after, number)})
	}

	switch name {
	case "EnhanceByWeapon", "EnhanceByMaterial":
		if strings.Contains(method, "WeaponService") {
			c.amount["weapon_enhance"]++
		}
	case "Enhance":
		switch {
		case strings.Contains(method, "CostumeService"):
			c.amount["costume_enhance"]++
		case strings.Contains(method, "CompanionService"):
			c.amount["companion_enhance"]++
		case strings.Contains(method, "PartsService"):
			c.amount["parts_enhance"]++
		}
	case "Buy":
		c.amount["shop_buy"]++
	case "FinishExplore":
		c.amount["explore_finish"]++
	case "FinishBigHuntQuest", "SkipBigHuntQuest":
		c.amount["big_hunt_play"]++
	case "UnlockLotteryEffectSlot":
		c.amount["lottery_slot"]++
	case "DrawLotteryEffect":
		c.amount["lottery_draw"]++
	case "Evolve":
		if r, ok := req.(*pb.EvolveRequest); ok {
			if w, ok := before.Weapons[r.UserWeaponUuid]; ok {
				add(c.byWeapon, "weapon_evolve", w.WeaponId, 1)
			}
		}
	}

	// Level and count changes on owned weapons and costumes.
	for id, w := range after.Weapons {
		old, had := before.Weapons[id]
		if !had {
			continue
		}
		add(c.byWeapon, "weapon_limit_break", old.WeaponId, int64(w.LimitBreakCount-old.LimitBreakCount))
		var sb, sa int32
		for _, s := range before.WeaponSkills[id] {
			sb += s.Level
		}
		for _, s := range after.WeaponSkills[id] {
			sa += s.Level
		}
		add(c.byWeapon, "weapon_skill", old.WeaponId, int64(sa-sb))
		if _, awake := after.WeaponAwakens[id]; awake {
			if _, was := before.WeaponAwakens[id]; !was {
				add(c.byWeapon, "weapon_awaken", w.WeaponId, 1)
			}
		}
	}
	for id, co := range after.Costumes {
		old, had := before.Costumes[id]
		if !had {
			continue
		}
		add(c.byCostume, "costume_limit_break", co.CostumeId, int64(co.LimitBreakCount-old.LimitBreakCount))
		add(c.byCostume, "costume_awaken", co.CostumeId, int64(co.AwakenCount-old.AwakenCount))
		add(c.byCostume, "costume_skill", co.CostumeId, int64(after.CostumeActiveSkills[id].Level-before.CostumeActiveSkills[id].Level))
	}
	for id, r := range after.CharacterRebirths {
		add(c.byChar, "character_rebirth", id, int64(r.RebirthCount-before.CharacterRebirths[id].RebirthCount))
	}
	if n := int64(after.Login.TotalLoginCount - before.Login.TotalLoginCount); n > 0 {
		c.amount["login"] += n
		c.amount["login_from_unlock"] += n
	}
	for id, b := range after.Gacha.BannerStates {
		n := int64(b.DrawCount - before.Gacha.BannerStates[id].DrawCount)
		if n <= 0 {
			continue
		}
		c.gacha[""] += n
		if GachaLabel != nil && GachaLabel(id) == model.GachaLabelChapter {
			c.gacha["chapter"] += n
		}
	}
	if n := int64(after.Gacha.TodaysCurrentDrawCount - before.Gacha.TodaysCurrentDrawCount); n > 0 {
		c.gacha["daily"] += n
	}
	return c
}

// amountFor is how much a request adds to one mission.
func (cat *Catalog) amountFor(m *Mission, c *counts) int64 {
	r := m.Rule
	switch r.Kind {
	case "quest":
		var n int64
		for _, q := range c.clears {
			if (r.NoSkip && q.skipped) || !cat.QuestMatches(r.Quest, q.questId) {
				continue
			}
			if len(r.Costumes) > 0 {
				found := false
				for _, co := range q.costumes {
					found = found || cat.CostumeMatches(r.Costumes, co)
				}
				if !found {
					continue
				}
			}
			n += q.count
		}
		return n
	case "stamina":
		var n int64
		for _, q := range c.clears {
			n += q.count * int64(cat.QuestStamina[q.questId])
		}
		return n
	case "gacha_draw":
		return c.gacha[r.Gacha]
	}
	if by, ok := c.byWeapon[r.Kind]; ok {
		var n int64
		for id, v := range by {
			if len(r.Weapons) == 0 || contains(r.Weapons, id) {
				n += v
			}
		}
		return n
	}
	if by, ok := c.byCostume[r.Kind]; ok {
		var n int64
		for id, v := range by {
			if cat.CostumeMatches(r.Costumes, id) {
				n += v
			}
		}
		return n
	}
	if by, ok := c.byChar[r.Kind]; ok {
		var n int64
		for id, v := range by {
			if len(r.Characters) == 0 || contains(r.Characters, id) {
				n += v
			}
		}
		return n
	}
	return c.amount[r.Kind]
}

// stateValue is the value of a mission read from the save.
func (cat *Catalog) stateValue(m *Mission, u *store.UserState) int64 {
	r := m.Rule
	var best int64
	switch r.Kind {
	case "user_level":
		return int64(u.Status.Level)
	case "costume_level", "costume_skill_level":
		for id, co := range u.Costumes {
			if !cat.CostumeMatches(r.Costumes, co.CostumeId) {
				continue
			}
			v := int64(co.Level)
			if r.Kind == "costume_skill_level" {
				v = int64(u.CostumeActiveSkills[id].Level)
			}
			best = max(best, v)
		}
	case "weapon_level", "weapon_skill_level", "weapon_ability_level":
		for id, w := range u.Weapons {
			if len(r.Weapons) > 0 && !contains(r.Weapons, w.WeaponId) {
				continue
			}
			switch r.Kind {
			case "weapon_level":
				best = max(best, int64(w.Level))
			case "weapon_skill_level":
				for _, s := range u.WeaponSkills[id] {
					best = max(best, int64(s.Level))
				}
			default:
				for _, s := range u.WeaponAbilities[id] {
					best = max(best, int64(s.Level))
				}
			}
		}
	case "favorite_character":
		if u.Profile.FavoriteCostumeId != 0 {
			return 1
		}
	case "board_panel":
		for _, b := range u.CharacterBoards {
			best += int64(bits.OnesCount32(uint32(b.PanelReleaseBit1)) + bits.OnesCount32(uint32(b.PanelReleaseBit2)) +
				bits.OnesCount32(uint32(b.PanelReleaseBit3)) + bits.OnesCount32(uint32(b.PanelReleaseBit4)))
		}
	case "big_hunt_score":
		for _, s := range u.BigHuntMaxScores {
			best = max(best, s.MaxScore)
		}
	case "max_deck_power":
		for _, n := range u.DeckTypeNotes {
			best = max(best, int64(n.MaxDeckPower))
		}
	}
	return best
}

// backfillValue is what a counted mission already has from the save when tracking starts.
func (cat *Catalog) backfillValue(m *Mission, u *store.UserState) int64 {
	r := m.Rule
	switch {
	case r.Kind == "quest" && len(r.Costumes) == 0 && !r.NoSkip:
		var n int64
		for id, q := range u.Quests {
			if q.ClearCount > 0 && cat.QuestMatches(r.Quest, id) {
				n += int64(q.ClearCount)
			}
		}
		return n
	case r.Kind == "login":
		return int64(u.Login.TotalLoginCount)
	}
	return 0
}

func (cat *Catalog) active(m *Mission, u *store.UserState, now int64) bool {
	if m.Start > now || (m.End != 0 && m.End <= now) {
		return false
	}
	switch m.Unlock.MissionUnlockConditionType {
	case unlockQuestClear:
		return u.Quests[m.Unlock.ConditionValue].ClearCount > 0
	case unlockMissionClearBy:
		return u.Missions[m.Unlock.ConditionValue].MissionProgressStatusType >= StatusClear
	}
	return true
}

// set writes a mission's progress, clearing it when it reaches its target.
func set(u *store.UserState, m *Mission, value int64, now int64) {
	rec, ok := u.Missions[m.MissionId]
	if rec.MissionProgressStatusType >= StatusClear {
		return
	}
	target := int64(m.ClearConditionValue)
	value = min(value, target, math.MaxInt32)
	if int64(rec.ProgressValue) == value && (ok || value == 0) {
		return
	}
	if !ok {
		rec = store.UserMissionState{MissionId: m.MissionId, StartDatetime: now, MissionProgressStatusType: StatusInProgress}
	}
	rec.ProgressValue = int32(value)
	if value >= target {
		rec.MissionProgressStatusType = StatusClear
		rec.ClearDatetime = now
	}
	rec.LatestVersion = now
	u.Missions[m.MissionId] = rec
}

// Track updates the save's missions for one request. before is the save before
// the request; after is the save after it, and is updated in place.
func (cat *Catalog) Track(before, after *store.UserState, method string, req any, now int64) {
	after.Ext.EnsureMaps()
	backfill := after.Ext.MissionsVersion < trackVersion
	today := startOfDay(now)
	recordLogin(after, now, today)
	c := collect(before, after, method, req)
	for _, m := range cat.Missions {
		if m.Rule.Kind == "" || m.Rule.Kind == "mission_clear" || m.Rule.Kind == "all_daily" || !cat.active(m, after, now) {
			continue
		}
		rec, ok := after.Missions[m.MissionId]
		if ok && m.Daily() && rec.StartDatetime < today {
			// A new day: daily missions start over.
			rec = store.UserMissionState{MissionId: m.MissionId, StartDatetime: now, MissionProgressStatusType: StatusInProgress, LatestVersion: now}
			after.Missions[m.MissionId] = rec
		}
		switch {
		case stateKinds[m.Rule.Kind]:
			set(after, m, cat.stateValue(m, after), now)
		case backfill && !m.Daily():
			set(after, m, max(int64(rec.ProgressValue), cat.backfillValue(m, after))+cat.amountFor(m, c), now)
		default:
			if n := cat.amountFor(m, c); n > 0 {
				set(after, m, int64(rec.ProgressValue)+n, now)
			}
		}
	}
	cat.trackCompletion(after, now, today)
	if backfill {
		// Level bonuses the save already had count as seen, so the game doesn't show them all again.
		for _, co := range after.Costumes {
			if _, ok := after.Ext.LevelBonusConfirmed[co.CostumeId]; !ok {
				after.Ext.LevelBonusConfirmed[co.CostumeId] = userdata.LevelBonusReleased(co.CostumeId, co.Level)
			}
		}
	}
	after.Ext.MissionsVersion = trackVersion
}

// recordLogin counts the day's first request as a login. Lunar Tear sets the
// login counts when it creates the player and never again, so the daily
// "Log in" missions would never clear after the first day.
func recordLogin(u *store.UserState, now, today int64) {
	l := &u.Login
	if l.LastLoginDatetime >= today {
		return
	}
	if l.LastLoginDatetime >= today-24*3600*1000 {
		l.ContinualLoginCount++
	} else {
		l.ContinualLoginCount = 1
	}
	l.MaxContinualLoginCount = max(l.MaxContinualLoginCount, l.ContinualLoginCount)
	l.TotalLoginCount++
	l.LastLoginDatetime = now
	l.LatestVersion = now
}

// trackCompletion updates the missions that count other missions.
func (cat *Catalog) trackCompletion(u *store.UserState, now, today int64) {
	var cleared int64
	dailyLeft := map[int32]int{} // sub category -> daily missions not cleared today
	for _, m := range cat.Missions {
		rec := u.Missions[m.MissionId]
		done := rec.MissionProgressStatusType >= StatusClear
		if done && !m.Daily() {
			cleared++
		}
		if m.Category == CategoryDaily && m.Rule.Kind != "all_daily" && cat.active(m, u, now) {
			if !done || rec.StartDatetime < today {
				dailyLeft[m.SubCategoryId]++
			} else {
				dailyLeft[m.SubCategoryId] += 0
			}
		}
	}
	for _, m := range cat.ByKind["mission_clear"] {
		if cat.active(m, u, now) {
			set(u, m, cleared, now)
		}
	}
	for _, m := range cat.ByKind["all_daily"] {
		if !cat.active(m, u, now) {
			continue
		}
		if rec, ok := u.Missions[m.MissionId]; ok && rec.StartDatetime < today {
			u.Missions[m.MissionId] = store.UserMissionState{MissionId: m.MissionId, StartDatetime: now, MissionProgressStatusType: StatusInProgress, LatestVersion: now}
		}
		left, any := dailyLeft[m.SubCategoryId]
		if m.MissionClearConditionType == 30 { // every daily mission
			left, any = 0, false
			for _, n := range dailyLeft {
				left += n
				any = true
			}
		}
		if any && left == 0 {
			set(u, m, int64(m.ClearConditionValue), now)
		}
	}
}
