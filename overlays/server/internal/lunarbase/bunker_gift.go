package lunarbase

// Pod Programs › Gift: gifts Bunker puts in the game's Gift Box, claimed there
// like any other gift (the game's claim rules apply), and how much of a thing
// can still be sent so that the gift can be claimed: the game claims a gift
// whole or not at all.

import (
	"errors"
	"fmt"
	"math"

	"github.com/google/uuid"

	"lunar-tear/server/internal/gametime"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/masterdata/memorydb"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/questflow"
	"lunar-tear/server/internal/runtime"
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

// BunkerGiftTextId is the m_gift_text row "From Bunker, with love." that the
// master-data patcher adds (patches/bunker-gift-text.patch).
const BunkerGiftTextId int32 = 90000

// BunkerGiftExpiry is when Bunker gifts expire: 2099-12-31 23:59:59 UTC, in
// effect never. The game's Gift Box fetches the list but shows nothing at all
// when a gift has no deadline (ExpirationDatetime 0), so it gets this one.
const BunkerGiftExpiry int64 = 4102444799000

// addBunkerGift puts an unclaimed Bunker gift in the gift box.
func addBunkerGift(user *store.UserState, t model.PossessionType, id, count int32, now int64) {
	user.Gifts.NotReceived = append(user.Gifts.NotReceived, store.NotReceivedGiftState{
		GiftCommon: store.GiftCommonState{
			PossessionType:        int32(t),
			PossessionId:          id,
			Count:                 count,
			GrantDatetime:         now,
			DescriptionGiftTextId: BunkerGiftTextId,
		},
		ExpirationDatetime: BunkerGiftExpiry,
		UserGiftUuid:       uuid.New().String(),
	})
	live := int32(0)
	for _, gift := range user.Gifts.NotReceived {
		if gift.ExpirationDatetime == 0 || gift.ExpirationDatetime >= now {
			live++
		}
	}
	user.Notifications.GiftNotReceiveCount = live
}

// waitingBunker counts what unclaimed Bunker gifts hold of a possession: of
// that id, or of the whole kind when byKind (weapons, memoirs).
func waitingBunker(user *store.UserState, t model.PossessionType, id int32, byKind bool) int64 {
	n := int64(0)
	for _, g := range user.Gifts.NotReceived {
		c := g.GiftCommon
		if c.DescriptionGiftTextId == BunkerGiftTextId && model.PossessionType(c.PossessionType) == t && (byKind || c.PossessionId == id) {
			n += int64(c.Count)
		}
	}
	return n
}

// giftRoom is how many more of a possession can be sent now so that every
// Bunker gift of it can be claimed. A possession the mods convert on arrival
// (g.Rewrite: stamina items as gold, tickets as gems) is checked as what
// arrives, as WouldOverflow does when the gift is claimed.
func giftRoom(user *store.UserState, g *store.PossessionGranter, t model.PossessionType, id int32) int64 {
	if g.Rewrite != nil {
		if rt, rid, each := g.Rewrite(t, id, 1); (rt != t || rid != id || each != 1) && each > 0 {
			room := rawGiftRoom(user, g, rt, rid) - waitingBunker(user, t, id, false)*int64(each)
			return max(room, 0) / int64(each)
		}
	}
	return rawGiftRoom(user, g, t, id)
}

func rawGiftRoom(user *store.UserState, g *store.PossessionGranter, t model.PossessionType, id int32) int64 {
	left := func(have int64, limit int32, waiting int64) int64 {
		if limit <= 0 {
			limit = math.MaxInt32
		}
		return max(int64(limit)-have-waiting, 0)
	}
	switch t {
	case model.PossessionTypeMaterial:
		return left(int64(user.Materials[id]), g.Limits.Material, waitingBunker(user, t, id, false))
	case model.PossessionTypeConsumableItem:
		limit := g.Limits.ConsumableItem
		switch {
		case id == g.GoldConsumableItemId && id != 0:
			limit = g.Limits.Money
		case g.GachaMedalItemIds[id]:
			limit = g.Limits.GachaMedal
		}
		return left(int64(user.ConsumableItems[id]), limit, waitingBunker(user, t, id, false))
	case model.PossessionTypeImportantItem:
		return left(int64(user.ImportantItems[id]), g.Limits.ImportantItem, waitingBunker(user, t, id, false))
	case model.PossessionTypePaidGem:
		return left(int64(user.Gem.PaidGem), 0, waitingBunker(user, t, id, true))
	case model.PossessionTypeFreeGem:
		return left(int64(user.Gem.FreeGem), 0, waitingBunker(user, t, id, true))
	case model.PossessionTypeWeapon:
		return left(int64(len(user.Weapons)), g.Limits.Weapon, waitingBunker(user, t, id, true))
	case model.PossessionTypeParts:
		return left(int64(len(user.Parts)), g.Limits.Parts, waitingBunker(user, t, id, true))
	case model.PossessionTypeCostume, model.PossessionTypeCompanion:
		return 1 // an owned one turns into its exchange items when claimed
	case model.PossessionTypeThought:
		for _, th := range user.Thoughts {
			if th.ThoughtId == id {
				return 0 // the game gives nothing for a second one
			}
		}
		if waitingBunker(user, t, id, false) > 0 {
			return 0
		}
		return 1
	}
	return 0
}

// sendGift checks a gift against giftRoom and puts it in the gift box.
func sendGift(user *store.UserState, g *store.PossessionGranter, t model.PossessionType, id, count int32, now int64) error {
	if count < 1 {
		return errors.New("count must be at least 1")
	}
	room := giftRoom(user, g, t, id)
	if room == 0 {
		return errors.New("nothing more of this can be claimed now")
	}
	if int64(count) > room {
		if room == 1 {
			return errors.New("only one can be sent at a time")
		}
		return fmt.Errorf("only %d more can be claimed now", room)
	}
	addBunkerGift(user, t, id, count, now)
	return nil
}

// LiveGranter, set by the app while its server runs (mobile.Edit), is the
// running server's granter: with its game data, limits and the mods'
// conversions. A gift's room is then read from it instead of loading the
// master data again, which would replace the server's shared tables.
var LiveGranter func() *store.PossessionGranter

// giftNow is the game's clock (the Original calendar's), as the server's.
func giftNow() int64 { return gametime.NowMillis() }

// giftGranter is the granter a gift is checked with: the running server's,
// else one built from the game data like the server's own.
func giftGranter(req *request) (*store.PossessionGranter, error) {
	if LiveGranter != nil {
		if g := LiveGranter(); g != nil {
			return g, nil
		}
	}
	if req.MasterDataPath == "" {
		return nil, errors.New("master_data_path required")
	}
	if err := memorydb.Init(req.MasterDataPath); err != nil {
		return nil, fmt.Errorf("init master data: %w", err)
	}
	partsCatalog, err := masterdata.LoadPartsCatalog()
	if err != nil {
		return nil, fmt.Errorf("load parts catalog: %w", err)
	}
	catalog, err := masterdata.LoadQuestCatalog(partsCatalog)
	if err != nil {
		return nil, fmt.Errorf("load quest catalog: %w", err)
	}
	gameConfig, err := masterdata.LoadGameConfig()
	if err != nil {
		return nil, fmt.Errorf("load game config: %w", err)
	}
	items, err := utils.ReadTable[masterdata.EntityMConsumableItem]("m_consumable_item")
	if err != nil {
		return nil, fmt.Errorf("load consumable items: %w", err)
	}
	g := questflow.BuildGranter(catalog, gameConfig)
	withLimits(g, gameConfig, items)
	g.Rewrite = runtime.ModRewrite(items, gameConfig.ConsumableItemIdForGold)
	return g, nil
}

// consumableItemTypeGachaMedal is ConsumableItemType GACHA_MEDAL.
const consumableItemTypeGachaMedal int32 = 120

// withLimits gives a granter the game data's possession limits, as the server
// does for its own (runtime.wireGranter): BuildGranter leaves them unset, and
// a gift past them could never be claimed.
func withLimits(g *store.PossessionGranter, cfg *masterdata.GameConfig, items []masterdata.EntityMConsumableItem) {
	g.Limits = store.PossessionLimits{
		Weapon:         cfg.PossessionCountLimitWeapon,
		Parts:          cfg.PossessionCountLimitParts,
		Material:       cfg.PossessionCountLimitMaterial,
		ConsumableItem: cfg.PossessionCountLimitConsumableItem,
		Money:          cfg.PossessionCountLimitMoney,
		ImportantItem:  cfg.PossessionCountLimitImportantItem,
		GachaMedal:     cfg.PossessionCountLimitGachaMedal,
	}
	if g.GoldConsumableItemId == 0 {
		g.GoldConsumableItemId = cfg.ConsumableItemIdForGold
	}
	g.GachaMedalItemIds = make(map[int32]bool)
	for _, it := range items {
		if it.ConsumableItemType == consumableItemTypeGachaMedal {
			g.GachaMedalItemIds[it.ConsumableItemId] = true
		}
	}
}

// runSendGift is the shim's "send_gift" action; applied is the count sent.
func runSendGift(req *request) (int, error) {
	g, err := giftGranter(req)
	if err != nil {
		return 0, err
	}
	db, st, err := openDB(req.DBPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	var refused error
	t := model.PossessionType(req.PossessionType)
	if _, err := st.UpdateUser(req.UserID, func(u *store.UserState) {
		refused = sendGift(u, g, t, req.PossessionID, req.Count, giftNow())
	}); err != nil {
		return 0, fmt.Errorf("send gift: %w", err)
	}
	if refused != nil {
		return 0, refused
	}
	return int(req.Count), nil
}

// runGiftRoom is the shim's "gift_room" action; applied is giftRoom. It reads
// the save without writing it.
func runGiftRoom(req *request) (int, error) {
	g, err := giftGranter(req)
	if err != nil {
		return 0, err
	}
	db, st, err := openDB(req.DBPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	user, err := st.LoadUser(req.UserID)
	if err != nil {
		return 0, fmt.Errorf("load user: %w", err)
	}
	return int(giftRoom(&user, g, model.PossessionType(req.PossessionType), req.PossessionID)), nil
}
