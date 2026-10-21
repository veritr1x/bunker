package masterdata

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"log"
	"strconv"
	"strings"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// summon_rules.json holds each summon's rules as the official notices (or,
// for 2021–22, outside sources: tweets, in-game screenshots, guides) state
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
}

type ruleFeatured struct {
	Costumes []int32 `json:"c"`
	Weapons  []int32 `json:"w"`
	Src      string  `json:"src"`
}

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
}

type summonRulesFile struct {
	Rules map[int32]summonRule
	New   []newSummon
}

func loadSummonRulesFile() (summonRulesFile, error) {
	var raw struct {
		Rules map[string]summonRule `json:"rules"`
		New   []newSummon           `json:"new"`
	}
	if err := json.Unmarshal(summonRulesJSON, &raw); err != nil {
		return summonRulesFile{}, fmt.Errorf("summon_rules.json: %w", err)
	}
	file := summonRulesFile{Rules: make(map[int32]summonRule, len(raw.Rules)), New: raw.New}
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
	return addNewSummons(entries, file, gametime.CalendarOffset())
}

// addNewSummons adds the recovered summons whose ids the game data doesn't
// use. offset moves their original dates to the calendar's current loop.
func addNewSummons(entries []store.GachaCatalogEntry, file summonRulesFile, offset int64) []store.GachaCatalogEntry {
	byId := make(map[int32]store.GachaCatalogEntry, len(entries))
	for _, e := range entries {
		byId[e.GachaId] = e
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
		pair, paired := byId[n.Pair]
		if paired {
			e.GachaMedalId, e.MedalConsumableItemId, e.CeilingCount = pair.GachaMedalId, pair.MedalConsumableItemId, pair.CeilingCount
			e.SortOrder, e.GachaDecorationType = pair.SortOrder, pair.GachaDecorationType
		}
		if n.Start == 0 {
			// No notice window: it ran with its regular summon (whose dates the calendar already moved).
			if !paired {
				continue
			}
			e.StartDatetime, e.EndDatetime = pair.StartDatetime, pair.EndDatetime
		}
		if n.Steps[0].Step > 0 {
			e.GachaModeType = model.GachaModeStepup
			e.GachaDecorationType = model.GachaDecorationFestival
		}
		rules[n.Id] = summonRule{Src: n.Src, Steps: n.Steps}
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
}

// applyNewFeatured gives each added summon its regular summon's lineup.
func (pool *GachaCatalog) applyNewFeatured(file summonRulesFile) {
	for _, n := range file.New {
		if fs, ok := pool.FeaturedByGacha[n.Pair]; ok && n.Pair != 0 {
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
		applied++
	}
	log.Printf("summon rules: %d summons featured as their notices list", applied)
}
