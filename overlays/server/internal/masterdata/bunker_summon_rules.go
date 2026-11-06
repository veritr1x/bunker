package masterdata

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"log"
	"slices"
	"sort"
	"strconv"
	"strings"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// summon_rules.json holds each summon's rules as the official notices (or,
// for 2021–22, outside sources: social posts, in-game screenshots, guides) state
// them: per draw or step its price, gem type, use limit, guarantee, ★4 rate
// and bonus items. It is compiled from the summon ledger outside this
// repository and carries facts only.
//
//go:embed summon_rules.json
var summonRulesJSON []byte

type ruleStep struct {
	Step   int32      `json:"step"`
	Draws  int32      `json:"draws"`
	Price  int32      `json:"price"`
	Cur    string     `json:"cur"` // gems, paid, free, ticket
	Limit  int32      `json:"limit"`
	Daily  bool       `json:"daily"`
	Guar   string     `json:"guar"`   // r3w, r4c, set10:feat, ... (see guaranteeRarity)
	Rate   float64    `json:"rate"`   // ★4 rate multiplier
	Set    []int32    `json:"set"`    // the costumes a set guarantee draws from
	Feat4  bool       `json:"feat4"`  // every ★4 drawn is a featured one
	Ticket int32      `json:"ticket"` // the ticket item a ticket draw takes (default: Premium Summon Ticket)
	Bonus  []string   `json:"bonus"`  // "Skip Ticket x100", as the notice says
	Items  []ruleItem `json:"items"`  // the same, as items
}

// ruleItem is a bonus item a draw gives: possession type, id and count.
type ruleItem struct {
	Type  int32 `json:"t"`
	Id    int32 `json:"id"`
	Count int32 `json:"n"`
}

// PhaseRule is what a draw's rule adds to its price phase: the guarantee,
// the set it draws from and the ★4 rate multiplier (0: no rate-up).
type PhaseRule struct {
	Guar  string
	Set   []int32
	Rate  float64
	Feat4 bool
}

var phaseRules = map[int32]PhaseRule{}

// PhaseRuleFor is the rule of a price phase, if its summon has rules.
func PhaseRuleFor(phaseId int32) (PhaseRule, bool) {
	r, ok := phaseRules[phaseId]
	return r, ok
}

type summonRule struct {
	Src      string        `json:"src"`
	Steps    []ruleStep    `json:"steps"`
	Featured *ruleFeatured `json:"featured"`
	// The notice's window (original game time), for a summon the game data
	// dates by its home banner, which showed for 3 days of a longer run.
	Start int64 `json:"start"`
	End   int64 `json:"end"`
	// W4Ability: every ★4 weapon the summon gives has this ability (a
	// barrier weapon summon's rank 4 barrier skill); they are its ★4 weapons.
	W4Ability int32 `json:"w4ability"`
	// W4: the ★4 weapons the summon gives, a listed selection (the Healer &
	// Support summons: their exchange's weapons of their elements).
	W4 []int32 `json:"w4"`
	// Notice: the summon's notice, over the notice pack's link (twins the
	// pack links the other way round).
	Notice int32 `json:"notice"`
}

type ruleFeatured struct {
	Costumes []int32 `json:"c"`
	Weapons  []int32 `json:"w"`
	Src      string  `json:"src"`
	// Only: the lineup is the summon's ★4 characters, not an addition to the
	// standard pool, and nothing is rated up (the Appreciation Gala's free
	// summons, each of one costume series).
	Only bool `json:"only"`
}

// onlyLineups are the summons whose ★4 characters are their lineup only.
var onlyLineups = map[int32]bool{}

// weaponLineup is a summon's ★4 weapons: those with an ability, or a list.
type weaponLineup struct {
	Ability int32
	Ids     []int32
}

// weaponLineups are the summons whose ★4 weapons are a lineup
// (summon_rules.json w4ability, w4).
var weaponLineups = map[int32]weaponLineup{}

// newSummon is a summon the game data lacks but its notice and banner art
// recover: the paid-only twins. Its window is the notice's (original game
// time); its pool and medal are its regular summon's (Pair).
type newSummon struct {
	Id     int32      `json:"id"`
	Asset  string     `json:"asset"`
	Pair   int32      `json:"pair"`
	Start  int64      `json:"start"`
	End    int64      `json:"end"`
	Notice int32      `json:"notice"`
	Src    string     `json:"src"`
	Steps  []ruleStep `json:"steps"`
	Prizes []Prize    `json:"prizes"` // a prize box summon
	Plain  bool       `json:"plain"`  // its art has no appeal/ panel: drawn in the normal (not festival) style
	Lineup int32      `json:"lineup"` // an earlier summon it reran: that summon's shards and lineup, its own dates
	Cards  []int32    `json:"cards"`  // the costumes its banner art shows, for its panel's cards
	Event  int32      `json:"event"`  // the event chapter its To Quests opens (a prize box: the daily quest that gave its tickets)
	// W4Ability: as summonRule's, for an added summon.
	W4Ability int32 `json:"w4ability"`
	// Medal: the medal (its consumable item) its art or notice names, when it
	// is neither a twin nor a rerun: a later volume of a notice whose first
	// volume has it, or a summon that gave the shard of another. It comes
	// from the summon the game data gives it to, or from its m_gacha_medal
	// row when that summon is not in the catalog (the Healer/Support medal
	// of 506 and 507, the weekly shards of 10107 and 10108).
	Medal int32 `json:"medal"`
}

// Prize is one prize of a prize box (Mama's Dream): what it gives and how
// many, its stock (0: never runs out) and, if unlimited, its weight.
type Prize struct {
	Name   string `json:"name"` // as the notice names it ("Gems")
	Type   int32  `json:"t"`
	Id     int32  `json:"id"`
	Qty    int32  `json:"n"`
	Stock  int32  `json:"stock"`
	Weight int32  `json:"w"`
}

var prizeBoxes = map[int32][]Prize{}

// plainSummons are the added summons whose art has no appeal images.
var plainSummons = map[int32]bool{}

// bannerCards are the costumes a plain summon's banner art shows.
var bannerCards = map[int32][]int32{}

// summonTitles are summon titles by banner asset (summon_rules.json titles),
// where the game text has none, has Japanese only, or names another summon
// (limited_416 and limited_417's are swapped; limited_428's names the summon
// a month later). archive/schedule.py keeps the same list for game-data summons.
var summonTitles = map[string]string{}

// SummonTitle is a summon's title from that list, or "".
func SummonTitle(asset string) string { return summonTitles[asset] }

// artCards are the costumes (or, for a weapon summon, the weapons) the game
// data's summons' appeal art shows, for the summons with no promotion cards
// (summon_rules.json art_cards).
var artCards = map[int32][]int32{}

// panelCards is how many promotion cards a plain summon's panel shows.
const panelCostumeCards, panelWeaponCards = 3, 2

// ApplyPanelPromotions gives each plain summon promotion cards, its panel's
// only content (the client has no appeal images for it): the characters its
// banner art shows when known, else ★4s its guaranteed slot can give, of its
// element if it names one, released ones only, newest first. They are not
// featured, so the draws keep the pool's odds. Elements come from
// ApplyRuleFeatured, which runs first.
func ApplyPanelPromotions(entries []store.GachaCatalogEntry, pool *GachaCatalog) {
	pool.applyOnlyLineups()
	pool.applyWeaponLineups(weaponLineups, weaponAbilities())
	// Released items: those some summon featured. The data also holds
	// costumes that never came out, with placeholder names.
	released := map[int32]bool{}
	for _, fs := range pool.FeaturedByGacha {
		for _, it := range fs.Costumes {
			released[it.PossessionId] = true
		}
		for _, it := range fs.Weapons {
			released[it.PossessionId] = true
		}
	}
	for i, e := range entries {
		if !plainSummons[e.GachaId] || len(e.PricePhases) == 0 {
			continue
		}
		if _, prize := PrizeBoxFor(e.GachaId); prize {
			continue
		}
		if ids := bannerCards[e.GachaId]; len(ids) > 0 {
			var cards []store.GachaPromotionItem
			for _, id := range ids {
				if c, ok := pool.CostumeById[id]; ok {
					cards = append(cards, toPromoItemWithBonus(c, pool))
				}
			}
			if len(cards) > 0 {
				entries[i].PromotionItems = cards
				continue
			}
		}
		rule, _ := PhaseRuleFor(e.PricePhases[0].PhaseId)
		kind, elemName, _ := strings.Cut(rule.Guar, ":")
		elem, byElement := ElementByName(strings.ToLower(elemName))
		pick := func(items []GachaPoolItem, n int) []store.GachaPromotionItem {
			var keep []GachaPoolItem
			for _, it := range items {
				if released[it.PossessionId] && (!byElement || ElementOf(it) == elem) {
					keep = append(keep, it)
				}
			}
			sort.Slice(keep, func(a, b int) bool { return keep[a].PossessionId > keep[b].PossessionId })
			var out []store.GachaPromotionItem
			for _, it := range keep[:min(n, len(keep))] {
				out = append(out, toPromoItemWithBonus(it, pool)) // a costume card carries its weapon
			}
			return out
		}
		costumes, weapons := pool.StandardCostumesByRarity[model.RaritySSRare], pool.StandardWeaponsByRarity[model.RaritySSRare]
		var cards []store.GachaPromotionItem
		switch kind {
		case "r4c":
			cards = pick(costumes, panelCostumeCards+panelWeaponCards)
		case "r4w":
			cards = pick(weapons, panelCostumeCards+panelWeaponCards)
		default:
			cards = append(pick(costumes, panelCostumeCards), pick(weapons, panelWeaponCards)...)
		}
		entries[i].PromotionItems = cards
	}
	applyArtCards(entries, artCards, pool)
}

// applyArtCards gives the summons with no promotion cards the characters
// their appeal art shows, in its order, with their weapons. Without a card the
// panel has one page (the appeal image), which the client's arrows turn onto
// itself and leave empty. They are not featured: the draws keep their odds.
func applyArtCards(entries []store.GachaCatalogEntry, cards map[int32][]int32, pool *GachaCatalog) {
	for i, e := range entries {
		if len(e.PromotionItems) > 0 {
			continue
		}
		for _, id := range cards[e.GachaId] {
			item, ok := pool.CostumeById[id]
			if !ok {
				item, ok = pool.WeaponById[id] // a weapon summon's art shows weapons
			}
			if ok {
				card := toPromoItemWithBonus(item, pool)
				card.IsTarget = false
				entries[i].PromotionItems = append(entries[i].PromotionItems, card)
			}
		}
	}
}

// applyOnlyLineups makes a summon's ★4 characters its lineup only (onlyLineups),
// once BuildBannerPools has added the lineup to the standard pool. The draws,
// Rates and panel all read the banner pool. ★3 characters and weapons stay.
func (pool *GachaCatalog) applyOnlyLineups() {
	for id := range onlyLineups {
		bp := pool.BannerPools[id]
		if bp == nil {
			continue
		}
		var lineup []GachaPoolItem
		for _, c := range pool.FeaturedByGacha[id].Costumes {
			if c.RarityType >= model.RaritySSRare {
				lineup = append(lineup, c)
			}
		}
		if len(lineup) > 0 {
			bp.CostumesByRarity[model.RaritySSRare] = lineup
		}
	}
}

// newWeaponLineups are the summons' weapon lineups: the rules' w4ability and
// w4, and an added summon's w4ability (only when the game data lacks that
// summon, so the entry is added; entries are the game data's summons).
func newWeaponLineups(file summonRulesFile, entries []store.GachaCatalogEntry) map[int32]weaponLineup {
	inData := map[int32]bool{}
	for _, e := range entries {
		inData[e.GachaId] = true
	}
	out := map[int32]weaponLineup{}
	for id, r := range file.Rules {
		if r.W4Ability != 0 || len(r.W4) > 0 {
			out[id] = weaponLineup{Ability: r.W4Ability, Ids: r.W4}
		}
	}
	for _, n := range file.New {
		if n.W4Ability != 0 && !inData[n.Id] {
			out[n.Id] = weaponLineup{Ability: n.W4Ability}
		}
	}
	return out
}

// applyWeaponLineups makes a summon's ★4 weapons its lineup: the ★4 weapons
// with its ability, or its listed ones, once BuildBannerPools has given it the
// standard pool. abilities is each weapon's abilities. Characters and ★3
// weapons stay.
func (pool *GachaCatalog) applyWeaponLineups(lineups map[int32]weaponLineup, abilities map[int32][]int32) {
	for id, l := range lineups {
		bp := pool.BannerPools[id]
		if bp == nil {
			continue
		}
		var lineup []GachaPoolItem
		// The pool's ★4 weapons: weapons kept out of every pool (restricted) stay out.
		for _, w := range pool.WeaponsByRarity[model.RaritySSRare] {
			if (l.Ability != 0 && slices.Contains(abilities[w.PossessionId], l.Ability)) || slices.Contains(l.Ids, w.PossessionId) {
				lineup = append(lineup, w)
			}
		}
		sort.Slice(lineup, func(a, b int) bool { return lineup[a].PossessionId < lineup[b].PossessionId })
		if len(lineup) > 0 {
			bp.WeaponsByRarity[model.RaritySSRare] = lineup
		}
	}
}

// weaponAbilities is each weapon's abilities, from the game data.
func weaponAbilities() map[int32][]int32 {
	out := map[int32][]int32{}
	if len(weaponLineups) == 0 {
		return out
	}
	groups, err := utils.ReadTable[EntityMWeaponAbilityGroup]("m_weapon_ability_group")
	if err != nil {
		return out
	}
	weapons, err := utils.ReadTable[EntityMWeapon]("m_weapon")
	if err != nil {
		return out
	}
	byGroup := map[int32][]int32{}
	for _, g := range groups {
		byGroup[g.WeaponAbilityGroupId] = append(byGroup[g.WeaponAbilityGroupId], g.AbilityId)
	}
	for _, w := range weapons {
		out[w.WeaponId] = byGroup[w.WeaponAbilityGroupId]
	}
	return out
}

// PrizeBoxFor is a prize box summon's prizes, if the summon is one.
func PrizeBoxFor(gachaId int32) ([]Prize, bool) {
	p, ok := prizeBoxes[gachaId]
	return p, ok
}

type summonRulesFile struct {
	Rules    map[int32]summonRule
	New      []newSummon
	ArtCards map[int32][]int32
}

func loadSummonRulesFile() (summonRulesFile, error) {
	var raw struct {
		Rules    map[string]summonRule `json:"rules"`
		New      []newSummon           `json:"new"`
		ArtCards map[string][]int32    `json:"art_cards"`
		Titles   map[string]string     `json:"titles"`
	}
	if err := json.Unmarshal(summonRulesJSON, &raw); err != nil {
		return summonRulesFile{}, fmt.Errorf("summon_rules.json: %w", err)
	}
	summonTitles = raw.Titles
	file := summonRulesFile{Rules: make(map[int32]summonRule, len(raw.Rules)), New: raw.New, ArtCards: map[int32][]int32{}}
	for k, ids := range raw.ArtCards {
		id, err := strconv.Atoi(k)
		if err != nil {
			return summonRulesFile{}, fmt.Errorf("summon_rules.json: art_cards summon id %q", k)
		}
		file.ArtCards[int32(id)] = ids
	}
	for k, r := range raw.Rules {
		id, err := strconv.Atoi(k)
		if err != nil {
			return summonRulesFile{}, fmt.Errorf("summon_rules.json: summon id %q", k)
		}
		file.Rules[int32(id)] = r
	}
	return file, nil
}

func loadSummonRules() (map[int32]summonRule, error) {
	file, err := loadSummonRulesFile()
	return file.Rules, err
}

// ApplySummonRules prices the catalog's summons by their recovered rules and
// adds the summons only the notices and banner art recover.
func ApplySummonRules(entries []store.GachaCatalogEntry) []store.GachaCatalogEntry {
	file, err := loadSummonRulesFile()
	if err != nil {
		log.Printf("summon rules off: %v", err)
		return entries
	}
	entries = applySummonRules(entries, file.Rules)
	artCards = file.ArtCards
	weaponLineups = newWeaponLineups(file, entries)
	if windows, err := loadMedalShopWindows(); err == nil {
		medalShopOpen = medalShopOpenFrom(windows)
	} else {
		log.Printf("summon rules: medal shops: %v", err)
	}
	if rows, err := utils.ReadTable[EntityMGachaMedal]("m_gacha_medal"); err == nil {
		medalRows = make(map[int32]EntityMGachaMedal, len(rows))
		for _, m := range rows {
			medalRows[m.ConsumableItemId] = m
		}
	} else {
		log.Printf("summon rules: medals: %v", err)
	}
	calendarOn := gametime.CurrentCalendar() != nil
	entries = applyNoticeWindows(entries, file.Rules, gametime.CalendarOffset(), calendarOn)
	entries = addNewSummonsFor(entries, file, gametime.CalendarOffset(), calendarOn)
	return withoutFalseSales(AddEventSummons(entries))
}

// withoutFalseSales leaves a price phase's regular price only where it is
// above the price. The client's draw button (GachaDrawButton.SetData) shows any
// regular price but 0 (kInvalidRegularPrice) as a sale, the regular price
// struck through beside the price; Lunar Tear gave every phase its own price
// as the regular one, so each summon read "300 300" and "3000 3000".
func withoutFalseSales(entries []store.GachaCatalogEntry) []store.GachaCatalogEntry {
	for i := range entries {
		for j := range entries[i].PricePhases {
			if p := &entries[i].PricePhases[j]; p.RegularPrice <= p.Price {
				p.RegularPrice = 0
			}
		}
	}
	return entries
}

// applyNoticeWindows runs the summons whose rule has a notice window for that
// window, moved by offset to the calendar's loop. With the calendar off the
// game data has every summon open, which stays.
func applyNoticeWindows(entries []store.GachaCatalogEntry, rules map[int32]summonRule, offset int64, calendarOn bool) []store.GachaCatalogEntry {
	if !calendarOn {
		return entries
	}
	for i := range entries {
		if r, ok := rules[entries[i].GachaId]; ok && r.Start > 0 && r.End > r.Start {
			entries[i].StartDatetime, entries[i].EndDatetime = r.Start+offset, r.End+offset
		}
	}
	return entries
}

// Without the Original calendar the game data has every summon open from
// 1999-12-31 to 2099-12-31; the added summons are open as long.
const (
	alwaysOpenStart int64 = 946598400000
	alwaysOpenEnd   int64 = 4102444799000
)

// ticketSummonSortOrder lists the always-open ticket summons after the
// summons of the day (the list goes by sort order, lowest first).
const ticketSummonSortOrder int32 = 1_000_000_000

func addNewSummons(entries []store.GachaCatalogEntry, file summonRulesFile, offset int64) []store.GachaCatalogEntry {
	return addNewSummonsFor(entries, file, offset, true)
}

// addNewSummonsFor adds the recovered summons whose ids the game data
// doesn't use. A twin runs with its regular summon (whose dates the calendar
// already moved). Others keep their own window, moved by offset to the
// calendar's loop, or with the calendar off are always open.
func addNewSummonsFor(entries []store.GachaCatalogEntry, file summonRulesFile, offset int64, calendarOn bool) []store.GachaCatalogEntry {
	byId := make(map[int32]store.GachaCatalogEntry, len(entries))
	byMedal := make(map[int32]store.GachaCatalogEntry)
	for _, e := range entries {
		byId[e.GachaId] = e
		if _, seen := byMedal[e.MedalConsumableItemId]; !seen && e.MedalConsumableItemId != 0 {
			byMedal[e.MedalConsumableItemId] = e
		}
	}
	rules := map[int32]summonRule{}
	var added []store.GachaCatalogEntry
	for _, n := range file.New {
		if _, taken := byId[n.Id]; taken || len(n.Steps) == 0 {
			continue
		}
		e := store.GachaCatalogEntry{
			GachaId:             n.Id,
			GachaLabelType:      model.GachaLabelPremium,
			GachaModeType:       model.GachaModeBasic,
			GachaAutoResetType:  model.GachaAutoResetNone,
			IsUserGachaUnlock:   true,
			StartDatetime:       n.Start + offset,
			EndDatetime:         n.End + offset,
			GachaDecorationType: model.GachaDecorationFestival,
			BannerAssetName:     n.Asset,
			GroupId:             n.Id,
			CeilingCount:        model.PityCeilingCount,
			UnlockConditionType: model.GachaUnlockNone,
			InformationId:       n.Notice,
		}
		if n.Plain {
			e.GachaDecorationType = model.GachaDecorationNormal
			plainSummons[n.Id] = true
			if len(n.Cards) > 0 {
				bannerCards[n.Id] = n.Cards
			}
		}
		if len(n.Prizes) > 0 {
			// An event summon: the client's box screen (appeal_background and
			// the prizes' stock) on the Event tab, which it unlocks.
			e.GachaLabelType, e.GachaModeType = model.GachaLabelEvent, model.GachaModeBox
		}
		// The Event tab shows To Quests; event chapter 0 opened the plain Event Quests list.
		e.RelatedEventQuestChapterId = n.Event
		if src, ok := byId[n.Lineup]; ok && n.Lineup != 0 {
			e.CeilingCount = src.CeilingCount
			// Its medal only while that medal's exchange is open for this
			// run: the client's Exchange otherwise opened an exchange with no shop.
			if medalShopOpen == nil || medalShopOpen(src.MedalConsumableItemId, n.Start+offset, n.End+offset) {
				e.GachaMedalId, e.MedalConsumableItemId = src.GachaMedalId, src.MedalConsumableItemId
			}
		}
		pair, paired := byId[n.Pair]
		if paired {
			e.GachaMedalId, e.MedalConsumableItemId, e.CeilingCount = pair.GachaMedalId, pair.MedalConsumableItemId, pair.CeilingCount
			e.SortOrder, e.GachaDecorationType = pair.SortOrder, pair.GachaDecorationType
		}
		// The medal its art names, once its exchange is open as the summon
		// starts. A run that outlasts the exchange (546) keeps giving it, as
		// the game did; the medal then waits for its conversion.
		if n.Medal != 0 && e.MedalConsumableItemId == 0 &&
			(medalShopOpen == nil || medalShopOpen(n.Medal, n.Start+offset, n.Start+offset)) {
			if owner, ok := byMedal[n.Medal]; ok {
				e.GachaMedalId, e.MedalConsumableItemId, e.CeilingCount = owner.GachaMedalId, owner.MedalConsumableItemId, owner.CeilingCount
			} else if row, ok := medalRows[n.Medal]; ok {
				e.GachaMedalId, e.MedalConsumableItemId, e.CeilingCount = row.GachaMedalId, row.ConsumableItemId, ceiling(row)
			}
		}
		switch {
		case paired:
			e.StartDatetime, e.EndDatetime = pair.StartDatetime, pair.EndDatetime
		case n.Start == 0:
			continue // runs with a regular summon the game data lacks
		case !calendarOn:
			e.StartDatetime, e.EndDatetime = alwaysOpenStart, alwaysOpenEnd
		}
		if !paired && n.Steps[0].Cur == "ticket" {
			e.SortOrder = ticketSummonSortOrder
		}
		if n.Steps[0].Step > 0 {
			e.GachaModeType = model.GachaModeStepup
			e.GachaDecorationType = model.GachaDecorationFestival
		}
		rules[n.Id] = summonRule{Src: n.Src, Steps: n.Steps, Notice: file.Rules[n.Id].Notice}
		if len(n.Prizes) > 0 {
			prizeBoxes[n.Id] = n.Prizes
		}
		added = append(added, e)
	}
	added = applySummonRules(added, rules)
	log.Printf("summon rules: %d summons added from notices and banner art", len(added))
	return append(entries, added...)
}

func priceTypeOf(cur string) int32 {
	switch cur {
	case "gems", "free":
		return model.PriceTypeGem
	case "paid":
		return model.PriceTypePaidGem
	case "ticket":
		return model.PriceTypeConsumableItem
	}
	return model.PriceTypeUnknown
}

// guaranteeRarity is the lowest rarity a rule's guaranteed slot gives:
// r3/r3w a ★3 or better, every ★4 rule (r4*, set10*, set_*) a ★4.
func guaranteeRarity(code string) int32 {
	switch {
	case code == "" || code == "none":
		return 0
	case strings.HasPrefix(code, "r3"):
		return model.RaritySRare
	}
	return model.RaritySSRare
}

func applySummonRules(entries []store.GachaCatalogEntry, rules map[int32]summonRule) []store.GachaCatalogEntry {
	applied := 0
	recorded := map[int32]PhaseRule{}
	for i := range entries {
		e := &entries[i]
		rule, ok := rules[e.GachaId]
		if ok && rule.Notice != 0 {
			e.InformationId = rule.Notice
		}
		if !ok || len(rule.Steps) == 0 {
			continue
		}
		stepped := rule.Steps[0].Step > 0
		if stepped != (e.GachaModeType == model.GachaModeStepup) {
			// A step-up needs its step pages in the client and a regular summon
			// has none, so the summon keeps its shape and prices.
			continue
		}
		var ticket []store.GachaPricePhaseEntry
		for _, p := range e.PricePhases {
			if p.PriceType == model.PriceTypeConsumableItem && !stepped {
				ticket = append(ticket, p)
			}
		}
		phases := make([]store.GachaPricePhaseEntry, 0, len(rule.Steps)+len(ticket))
		daily := false
		for n, s := range rule.Steps {
			p := store.GachaPricePhaseEntry{
				PhaseId:        e.GachaId*model.PhaseIdMultiplier + int32(n+1),
				PriceType:      priceTypeOf(s.Cur),
				Price:          s.Price,
				RegularPrice:   s.Price,
				DrawCount:      s.Draws,
				LimitExecCount: s.Limit,
				StepNumber:     s.Step,
			}
			for _, b := range s.Items {
				p.Bonuses = append(p.Bonuses, store.GachaBonusEntry{PossessionType: b.Type, PossessionId: b.Id, Count: b.Count})
			}
			if s.Cur == "ticket" {
				p.PriceId = model.ConsumableIdPremiumTicket
				if s.Ticket > 0 {
					p.PriceId = s.Ticket
				}
			}
			if min := guaranteeRarity(s.Guar); min > 0 {
				p.FixedRarityMin, p.FixedCount = min, 1
			}
			if stepped {
				p.LimitExecCount = 1
			}
			if s.Daily {
				daily = true
				if p.LimitExecCount == 0 {
					p.LimitExecCount = 1
				}
			}
			phases = append(phases, p)
			recorded[p.PhaseId] = PhaseRule{Guar: s.Guar, Set: s.Set, Rate: s.Rate, Feat4: s.Feat4}
		}
		for _, t := range ticket {
			if len(phases) == int(model.PhaseIdMultiplier)-1 {
				break
			}
			t.PhaseId = e.GachaId*model.PhaseIdMultiplier + int32(len(phases)+1)
			phases = append(phases, t)
		}
		e.PricePhases = phases
		if stepped {
			e.MaxStepNumber = int32(len(rule.Steps))
		}
		if daily {
			e.GachaAutoResetType, e.GachaAutoResetPeriod = model.GachaAutoResetDaily, 1
		}
		applied++
	}
	for id, r := range recorded {
		phaseRules[id] = r
	}
	log.Printf("summon rules: %d summons priced from notices and other sources", applied)
	return entries
}

// ApplyRuleFeatured sets each summon's featured characters and weapons to
// its notice's lineup (else what outside sources name), in place of the
// lineup worked out from the game's catalog terms. Run it before
// BuildBannerPools.
func (pool *GachaCatalog) ApplyRuleFeatured() {
	file, err := loadSummonRulesFile()
	if err != nil {
		log.Printf("summon rules off: %v", err)
		return
	}
	pool.applyRuleFeatured(file.Rules)
	pool.applyNewFeatured(file)
	pool.loadElements()
}

// applyNewFeatured gives each added summon its regular summon's lineup,
// unless its rule lists a lineup of its own (another volume of a summon).
func (pool *GachaCatalog) applyNewFeatured(file summonRulesFile) {
	for _, n := range file.New {
		if r, ok := file.Rules[n.Id]; ok && r.Featured != nil {
			continue
		}
		if fs, ok := pool.FeaturedByGacha[n.Pair]; ok && n.Pair != 0 {
			pool.FeaturedByGacha[n.Id] = fs
		} else if fs, ok := pool.FeaturedByGacha[n.Lineup]; ok && n.Lineup != 0 {
			pool.FeaturedByGacha[n.Id] = fs
		}
	}
}

func (pool *GachaCatalog) applyRuleFeatured(rules map[int32]summonRule) {
	if pool.FeaturedByGacha == nil {
		pool.FeaturedByGacha = map[int32]FeaturedSet{}
	}
	applied := 0
	for id, r := range rules {
		if r.Featured == nil {
			continue
		}
		var fs FeaturedSet
		paired := map[int32]bool{}
		for _, cid := range r.Featured.Costumes {
			if c, ok := pool.CostumeById[cid]; ok {
				fs.Costumes = append(fs.Costumes, c)
				if wid, ok := pool.CostumeWeaponMap[cid]; ok {
					paired[wid] = true
				}
			}
		}
		for _, wid := range r.Featured.Weapons {
			if w, ok := pool.WeaponById[wid]; ok && !paired[wid] {
				fs.Weapons = append(fs.Weapons, w)
			}
		}
		if len(fs.Costumes) == 0 && len(fs.Weapons) == 0 {
			continue
		}
		if !strings.HasPrefix(r.Featured.Src, "notice") && len(r.Featured.Weapons) == 0 {
			// Outside sources name the characters only; the featured weapons stay.
			for _, w := range pool.FeaturedByGacha[id].Weapons {
				if !paired[w.PossessionId] {
					fs.Weapons = append(fs.Weapons, w)
				}
			}
		}
		pool.FeaturedByGacha[id] = fs
		if r.Featured.Only {
			onlyLineups[id] = true
		}
		applied++
	}
	log.Printf("summon rules: %d summons featured as their notices list", applied)
}

// medalShopOpen is whether an exchange shop taking a medal is open for a whole
// run (game data dates); nil: always. ApplySummonRules sets it.
var medalShopOpen func(item int32, start, end int64) bool

// medalRows are the game data's medals (m_gacha_medal), by their item.
// ApplySummonRules sets them.
var medalRows map[int32]EntityMGachaMedal

func medalShopOpenFrom(windows map[int32][][2]int64) func(int32, int64, int64) bool {
	return func(item int32, start, end int64) bool {
		for _, w := range windows[item] {
			if w[0] <= start && end <= w[1] {
				return true
			}
		}
		return false
	}
}

// loadMedalShopWindows is when each shop selling for an item is open, by the
// item it takes (the client's CalculatorShop.GetShopIdByConsumableItemId looks
// for an open shop this way).
func loadMedalShopWindows() (map[int32][][2]int64, error) {
	shops, err := utils.ReadTable[EntityMShop]("m_shop")
	if err != nil {
		return nil, err
	}
	groups, err := utils.ReadTable[EntityMShopItemCellGroup]("m_shop_item_cell_group")
	if err != nil {
		return nil, err
	}
	cells, err := utils.ReadTable[EntityMShopItemCell]("m_shop_item_cell")
	if err != nil {
		return nil, err
	}
	items, err := utils.ReadTable[EntityMShopItem]("m_shop_item")
	if err != nil {
		return nil, err
	}
	price := make(map[int32]int32, len(items))
	for _, it := range items {
		if it.PriceType == model.PriceTypeConsumableItem {
			price[it.ShopItemId] = it.PriceId
		}
	}
	cellPrices := map[int32][]int32{}
	for _, c := range cells {
		if p, ok := price[c.ShopItemId]; ok {
			cellPrices[c.ShopItemCellId] = append(cellPrices[c.ShopItemCellId], p)
		}
	}
	groupPrices := map[int32]map[int32]bool{}
	for _, g := range groups {
		for _, p := range cellPrices[g.ShopItemCellId] {
			if groupPrices[g.ShopItemCellGroupId] == nil {
				groupPrices[g.ShopItemCellGroupId] = map[int32]bool{}
			}
			groupPrices[g.ShopItemCellGroupId][p] = true
		}
	}
	out := map[int32][][2]int64{}
	for _, s := range shops {
		for p := range groupPrices[s.ShopItemCellGroupId] {
			out[p] = append(out[p], [2]int64{s.StartDatetime, s.EndDatetime})
		}
	}
	return out, nil
}
