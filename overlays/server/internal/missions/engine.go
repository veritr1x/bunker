package missions

import (
	"math"
	"math/bits"
	"strings"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/userdata"
)

// trackVersion is stored in ExtState.MissionsVersion once a save's missions
// have been backfilled from what the player already did.
const trackVersion = 4

// kindVersion is the trackVersion that last changed a kind's rules: a save
// tracked by an older version backfills that kind's missions once from the
// save. Version 3 added quest rules for missions that had none; version 4
// more of them (and EX Hard quest places), profile messages and the play history.
var kindVersion = map[string]int32{
	"quest": 4, "login": 1,
	"pvp_play": 2, "pvp_win": 2, "pvp_streak": 2,
	"user_message": 4,
}

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
	"library": true, "costume_ability_level": true, "report": true, "explore_score": true,
	"pvp_rank": true, "data_transfer": true, "costume_collect": true,
}

// Kinds whose progress is the best single value seen, not a sum.
var bestKinds = map[string]bool{"rhythm_tap": true}

// Arena win streaks: a win adds one, a loss starts over.
var streakKinds = map[string]bool{"pvp_streak": true, "pvp_streak_from_unlock": true}

// counts holds what one request added, per kind; a mission's own filter picks
// the entries it counts.
type counts struct {
	clears    []questClear
	amount    map[string]int64
	byWeapon  map[string]map[int32]int64 // kind -> weapon id -> amount
	byCostume map[string]map[int32]int64
	byChar    map[string]map[int32]int64
	gacha     map[string]int64                      // "" all, "daily", "chapter"
	explores  map[int32]int64                       // explore id -> explorations finished
	rhythm    map[int32]int64                       // concert LiveType -> taps in one performance
	pvp       int                                   // an Arena battle: pvpWin or pvpLoss
	message   *string                               // the profile message set
	tutorials map[int32]store.TutorialProgressState // tutorials played, after the request
}

const (
	pvpWin  = 1
	pvpLoss = -1
)

type questClear struct {
	questId  int32
	count    int64
	skipped  bool
	costumes []int32
}

func newCounts() *counts {
	return &counts{amount: map[string]int64{}, byWeapon: map[string]map[int32]int64{},
		byCostume: map[string]map[int32]int64{}, byChar: map[string]map[int32]int64{}, gacha: map[string]int64{},
		explores: map[int32]int64{}, rhythm: map[int32]int64{}}
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
	return gametime.StartOfDay(now)
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
		if v := r.PictureBookMeasurableValues; v != nil {
			c.amount["defeat_wizard"] += int64(v.DefeatWizardCount)
			if t := v.RhythmInteractionMeasurableValues; t != nil {
				c.rhythm[t.LiveTypeId] = max(c.rhythm[t.LiveTypeId], int64(t.TapCount))
			}
		}
	case *pb.FinishExploreRequest:
		c.explores[r.ExploreId]++
		c.amount["explore_score_total"] += int64(max(0, r.Score))
	case *pb.SetUserMessageRequest:
		c.message = &r.Message
	}
	c.tutorials = after.Tutorials
	// The cage's walk and Mama-tap counters ride on several requests
	// (UpdateMissionProgress, GetMamaBanner, GetFriendList, ...); the client
	// clears them once sent.
	if r, ok := req.(interface {
		GetCageMeasurableValues() *pb.CageMeasurableValues
	}); ok {
		if v := r.GetCageMeasurableValues(); v != nil {
			c.amount["cage_walk"] += int64(v.RunningDistanceMeters)
			c.amount["mama_tap"] += int64(v.MamaTappedCount)
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
	case "GameStart":
		// The game starts from the title screen.
		c.amount["title_transition"]++
	case "Buy":
		c.amount["shop_buy"]++
	case "FinishBigHuntQuest", "SkipBigHuntQuest":
		c.amount["big_hunt_play"]++
		// Knockdowns saved during the battle (SaveBigHuntBattleInfo); finishing clears them.
		if name == "FinishBigHuntQuest" && !before.BigHuntProgress.IsDryRun {
			c.amount["big_hunt_knockdown"] += int64(before.BigHuntBattleDetail.BossKnockDownCount)
		}
	case "FinishBattle":
		// An Arena battle the player started: Finish adds it to the attack log.
		if strings.Contains(method, "PvpService") {
			if l := after.Ext.Pvp.AttackLog; len(l) > 0 && (len(before.Ext.Pvp.AttackLog) == 0 || before.Ext.Pvp.AttackLog[0] != l[0]) {
				c.amount["pvp_play"]++
				c.pvp = pvpLoss
				if l[0].Victory {
					c.amount["pvp_win"]++
					c.pvp = pvpWin
				}
			}
		}
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
		if w.IsProtected && !old.IsProtected {
			c.amount["weapon_protect"]++
		}
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
	if n := after.Ext.Friends.TotalSent - before.Ext.Friends.TotalSent; n > 0 {
		c.amount["cheer_friend"] += n
	}
	return c
}

// amountFor is how much a request adds to one mission.
func (cat *Catalog) amountFor(m *Mission, c *counts) int64 {
	r := m.Rule
	switch r.Kind {
	case "quest":
		if playedAny(r.NoTutorials, c.tutorials) {
			return 0
		}
		var n int64
		for _, q := range c.clears {
			if (r.NoSkip && q.skipped) || !cat.QuestMatches(r.Quest, q.questId) {
				continue
			}
			if len(r.Costumes) > 0 {
				found, all := false, len(q.costumes) > 0
				for _, co := range q.costumes {
					match := cat.CostumeMatches(r.Costumes, co)
					found, all = found || match, all && match
				}
				if !found || (r.Only && !all) {
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
	case "defeat_boss":
		// The bosses of each quest won in battle; a skip fights none.
		var n int64
		for _, q := range c.clears {
			if !q.skipped {
				n += q.count * cat.questBosses[q.questId]
			}
		}
		return n
	case "explore_finish":
		var n int64
		for id, v := range c.explores {
			if len(r.Explores) == 0 || contains(r.Explores, id) {
				n += v
			}
		}
		return n
	case "rhythm_tap":
		return c.rhythm[r.LiveType]
	case "gacha_draw":
		return c.gacha[r.Gacha]
	case "user_message":
		if c.message != nil && messageMatches(r.Word, *c.message) {
			return 1
		}
		return 0
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
		for id, b := range u.CharacterBoards {
			place := cat.boards[id]
			if (len(r.Characters) > 0 && !contains(r.Characters, place.CharacterId)) ||
				(len(r.BoardTypes) > 0 && !contains(r.BoardTypes, place.GroupType)) {
				continue
			}
			best += int64(bits.OnesCount32(uint32(b.PanelReleaseBit1)) + bits.OnesCount32(uint32(b.PanelReleaseBit2)) +
				bits.OnesCount32(uint32(b.PanelReleaseBit3)) + bits.OnesCount32(uint32(b.PanelReleaseBit4)))
		}
	case "big_hunt_score":
		for boss, s := range u.BigHuntMaxScores { // by BigHuntBossId
			if len(r.Bosses) == 0 || contains(r.Bosses, boss) {
				best = max(best, s.MaxScore)
			}
		}
	case "explore_score":
		for id, s := range u.ExploreScores {
			if len(r.Explores) == 0 || contains(r.Explores, id) {
				best = max(best, int64(s.MaxScore))
			}
		}
	case "costume_ability_level":
		// Character abilities are levelled on the Mythic Slab.
		for _, a := range u.CharacterBoardAbilities {
			best = max(best, int64(a.Level))
		}
	case "report":
		// Hidden Stories: important items that carry a report (m_important_item.ReportId).
		for id, n := range u.ImportantItems {
			if n > 0 && cat.reportItems[id] {
				best++
			}
		}
	case "library":
		return cat.encyclopediaEntries(u)
	case "pvp_rank":
		// "Reach rank N": the client shows 0/1 (m_mission_clear_condition_value_view).
		if rank := u.Ext.Pvp.MaxSeasonRank; rank > 0 && rank <= m.ClearConditionValue {
			return int64(m.ClearConditionValue)
		}
	case "data_transfer":
		if u.FacebookId != 0 {
			return 1
		}
	case "max_deck_power":
		for _, n := range u.DeckTypeNotes {
			best = max(best, int64(n.MaxDeckPower))
		}
	case "costume_collect":
		// The costumes m_complete_mission_group lists, owned. The client shows
		// them from the master data (IUserMissionCompletionProgress has no
		// lookup in the client), so only the count is kept.
		owned := map[int32]bool{}
		for _, co := range u.Costumes {
			owned[co.CostumeId] = true
		}
		for _, id := range r.Costumes {
			if owned[id] {
				best++
			}
		}
	}
	return best
}

// playedAny reports whether the player has played any of these tutorials.
func playedAny(tutorials []int32, played map[int32]store.TutorialProgressState) bool {
	for _, t := range tutorials {
		if _, ok := played[t]; ok {
			return true
		}
	}
	return false
}

// messageMatches reports whether a profile message counts for a mission:
// any message without words, else one containing them (case and spacing aside).
func messageMatches(word, message string) bool {
	message = strings.Join(strings.Fields(strings.ToLower(strings.ReplaceAll(message, "’", "'"))), " ")
	return message != "" && strings.Contains(message, word)
}

// encyclopediaEntries counts what the player has in the Encyclopedia: costumes,
// weapons (ever obtained), companions, parts and memoirs it lists.
func (cat *Catalog) encyclopediaEntries(u *store.UserState) int64 {
	e := cat.encyclopedia
	seen := map[[2]int32]bool{}
	note := func(kind, id int32, listed map[int32]bool) {
		if listed[id] {
			seen[[2]int32{kind, id}] = true
		}
	}
	for _, co := range u.Costumes {
		note(1, co.CostumeId, e.costumes)
	}
	for id := range u.WeaponNotes {
		note(2, id, e.weapons)
	}
	for _, w := range u.Weapons {
		note(2, w.WeaponId, e.weapons)
	}
	for _, co := range u.Companions {
		note(3, co.CompanionId, e.companions)
	}
	for id := range u.PartsGroupNotes {
		note(4, id, e.partsGroups)
	}
	for _, t := range u.Thoughts {
		note(5, t.ThoughtId, e.thoughts)
	}
	return int64(len(seen))
}

// backfillValue is what a counted mission already has from the save when tracking starts.
func (cat *Catalog) backfillValue(m *Mission, u *store.UserState) int64 {
	r := m.Rule
	switch {
	case r.Kind == "quest" && len(r.Costumes) == 0 && !r.NoSkip:
		if playedAny(r.NoTutorials, u.Tutorials) {
			return 0
		}
		var n int64
		for id, q := range u.Quests {
			if q.ClearCount > 0 && cat.QuestMatches(r.Quest, id) {
				n += int64(q.ClearCount)
			}
		}
		return n
	case r.Kind == "login":
		return int64(u.Login.TotalLoginCount)
	case r.Kind == "user_message":
		if messageMatches(r.Word, u.Profile.Message) {
			return 1
		}
	// The Arena keeps this season's results.
	case r.Kind == "pvp_play":
		return int64(u.Ext.Pvp.Season.AttackWins + u.Ext.Pvp.Season.AttackLosses)
	case r.Kind == "pvp_win":
		return int64(u.Ext.Pvp.Season.AttackWins)
	case r.Kind == "pvp_streak":
		return int64(u.Ext.Pvp.WinStreak)
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
	tracked := after.Ext.MissionsVersion
	today := startOfDay(now)
	recordLogin(after, now, today)
	recordLastDeck(after, req)
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
		case tracked < kindVersion[m.Rule.Kind] && !m.Daily():
			// The backfill reads the save before this request; amountFor adds what the request did.
			set(after, m, max(int64(rec.ProgressValue), cat.backfillValue(m, before))+cat.amountFor(m, c), now)
		case streakKinds[m.Rule.Kind]:
			switch c.pvp {
			case pvpWin:
				set(after, m, int64(rec.ProgressValue)+1, now)
			case pvpLoss:
				set(after, m, 0, now)
			}
		case bestKinds[m.Rule.Kind]:
			if n := cat.amountFor(m, c); n > int64(rec.ProgressValue) {
				set(after, m, n, now)
			}
		default:
			if n := cat.amountFor(m, c); n > 0 {
				set(after, m, int64(rec.ProgressValue)+n, now)
			}
		}
	}
	cat.trackCompletion(after, now, today)
	cat.recordHistory(before, after, c, method, req, tracked < 4)
	if tracked < 1 {
		// Level bonuses the save already had count as seen, so the game doesn't show them all again.
		for _, co := range after.Costumes {
			if _, ok := after.Ext.LevelBonusConfirmed[co.CostumeId]; !ok {
				after.Ext.LevelBonusConfirmed[co.CostumeId] = userdata.LevelBonusReleased(co.CostumeId, co.Level)
			}
		}
	}
	after.Ext.MissionsVersion = trackVersion
}

// recordLastDeck notes the deck a battle is fought with (the client's own
// account of its party in FinishWave), for the profile card.
func recordLastDeck(u *store.UserState, req any) {
	r, ok := req.(*pb.FinishWaveRequest)
	if !ok {
		return
	}
	for _, p := range r.UserPartyResultInfoList {
		if p.UserDeckNumber != 0 {
			u.Ext.LastDeck = store.LastDeckState{DeckType: p.DeckType, UserDeckNumber: p.UserDeckNumber}
			return
		}
	}
}

// recordLogin counts the day's first request as a login. Lunar Tear sets the
// login counts when it creates the player and never again, so the daily
// "Log in" missions would never clear after the first day.
func recordLogin(u *store.UserState, now, today int64) {
	l := &u.Login
	if l.LastLoginDatetime >= today {
		return
	}
	campaign.JoinComeback(u, l.LastLoginDatetime, now)
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
