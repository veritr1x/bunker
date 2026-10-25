"""The live service's dated content for the Archive's Schedule pages: summons, events, shops, home
banners and the rest, with their original dates from the master data."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from .memo import memo

LAUNCH = int(datetime(2021, 7, 28, 2, tzinfo=timezone.utc).timestamp() * 1000)  # global launch
# Dates from June 2024 on are placeholders: the service ended in April 2024.
FOREVER = int(datetime(2024, 6, 1, tzinfo=timezone.utc).timestamp() * 1000)
DAY = 24 * 60 * 60 * 1000
EARLIEST = int(datetime(2000, 1, 2, tzinfo=timezone.utc).timestamp() * 1000)

# Tables the Schedule reads; the index keeps them (index.MASTER_TABLES).
TABLES = ("m_mom_banner", "m_gacha_medal", "m_event_quest_chapter", "m_event_quest_sequence_group",
          "m_event_quest_sequence", "m_quest", "m_event_quest_labyrinth_season", "m_shop", "m_shop_item",
          "m_shop_item_cell", "m_shop_item_cell_group", "m_shop_item_cell_term", "m_shop_item_content_possession",
          "m_shop_item_limited_stock", "m_consumable_item", "m_material", "m_important_item", "m_weapon",
          "m_parts", "m_parts_group", "m_thought", "m_costume_enhanced", "m_companion_enhanced",
          "m_login_bonus", "m_pvp_season", "m_big_hunt_schedule", "m_mission_pass", "m_quest_campaign",
          "m_quest_campaign_effect_group", "m_enhance_campaign", "m_omikuji", "m_comeback_campaign",
          "m_event_quest_guerrilla_free_open")

TABS = (("timeline", "Timeline"), ("summons", "Summons"), ("events", "Events"), ("shops", "Shops"),
        ("banners", "Banners"), ("other", "Other"))
EVENT_TYPES = {1: "Record", 2: "Variation", 3: "Remnant", 4: "Daily", 5: "Guerrilla", 6: "Character Quest",
               7: "Character Quest", 8: "Hidden", 9: "Special", 10: "Abyss Tower", 11: "Chambers of Dusk",
               12: "Fate Board"}
SHOP_TYPES = {1: "Gems", 3: "Item Shop", 4: "Exchange", 5: "Recovery", 6: "Recovery", 7: "Packs", 9: "Mission packs",
              10: "Mama's Choice", 11: "Monthly pass"}
BANNER_TARGETS = {1: "Summon", 2: "Shop", 21: "Link", 22: "Missions", 23: "Announcement", 27: "Panel mission"}
# The server's medal links (server/internal/masterdata/gacha.go): summons sharing another summon's
# medal, and summons whose medal is known only by its shard item.
SHARED_MEDALS = {46: 45, 151: 150}
MEDAL_ITEMS = {401: 8087, 501: 8168, 535: 8192, 541: 8192, 542: 8192, 543: 8193, 549: 8197, 550: 8197,
               555: 8203, 556: 8203, 582: 8222, 583: 8222, 585: 8222, 510001: 8030, 513001: 8033,
               515001: 8045, 536001: 8110, 537001: 8133, 9000035: 8021}
# Summons the game text has no title for: the title is drawn into the banner art only (read from
# ui/gacha/en/<asset>/mom_banner). Keyed by banner asset.
ART_TITLES = {
    "limited_71": "Elemental Summons", "limited_9001": "Halloween Lucky Summons", "limited_84": "Halloween Bonus Summons",
    "step_up_501001": "Black Friday Multi-Step Summons", "limited_9004": "NieR Day Bonus Summons",
    "limited_9005": "★★★★ Guaranteed Fire-Elemental Holiday Summons (Paid Gems Only)",
    "limited_9006": "★★★★ Guaranteed Light-Elemental Holiday Summons (Paid Gems Only)",
    "limited_9007": "★★★★ Guaranteed Wind-Elemental Holiday Summons (Paid Gems Only)",
    "limited_9008": "★★★★ Guaranteed Water-Elemental Holiday Summons (Paid Gems Only)",
    "limited_9009": "★★★★ Guaranteed Dark-Elemental Holiday Summons (Paid Gems Only)",
    "limited_9010": "The Sun and the Moon Release Countdown Summons Vol. 1",
    "limited_9011": "The Sun and the Moon Release Countdown Summons Vol. 2",
    "limited_9012": "The Sun and the Moon Release Countdown Summons Vol. 3",
    "limited_9013": "The Sun and the Moon Release Countdown Summons Vol. 4",
    "limited_9014": "Subjugation Bonus Summons", "limited_9015": "NieR Day Bonus Summons",
    "step_up_900001": "Subjugation Multi-Step Summons", "limited_9017": "Hunter Summons", "limited_9018": "Subjugation Bonus Summons",
    "limited_9019": "Daily Showcase Summons Vol. 1", "limited_9020": "Daily Showcase Summons Vol. 2",
    "limited_9021": "Daily Showcase Summons Vol. 3", "limited_9022": "Daily Showcase Summons Vol. 4",
    "limited_9023": "Daily Showcase Summons Vol. 5", "step_up_511001": "Anniversary ★★★★ Guaranteed Summons (Paid Gems Only)",
    "limited_9026": "NieR Day Bonus Summons", "limited_9027": "NieR Day Bonus Summons", "limited_9028": "NieR Day Bonus Summons",
    "step_up_514001": "Arena Update Celebration Multi-Step Summons",
    "step_up_522001": "Crossover Quest Support Paid-Only Multi-Step Summons",
    "step_up_525001": "The Sun and the Moon New Chapter Multi-Step Summons",
    "step_up_533001": "Japanese 1.5-Year Anniversary Recollections of Dusk Summons (Paid-Only Multi-Step)",
    "limited_405": "Japanese 1.5-Year Anniversary Abyssal Costume Summons (Paid Gems Only)",
    "step_up_527001": "Crossover Quest Support Paid-Only Multi-Step Summons",
    "step_up_534001": "Monthly Featured Paid-Only Multi-Step Summons",
    "limited_415": "The Sun and the Moon New Chapter ★★★★ Character Guaranteed Summons (Paid Gems Only)",
    "limited_456": "New Year's Celebration Free 10x Summons Daily", "limited_457": "New Year's Celebration Free 10x Summons Daily",
    "step_up_551001": "Monthly Featured Paid-Only Multi-Step Summons", "limited_506": "Healer/Support ★★★★ Guaranteed Summons",
    "common_200001": "Japanese 2.5 Year Anniversary Mama's Dream Summons",
    "limited_554": "Dragon Quest X Crossover Commemorative 10 Free Summons",
    "limited_576": "Japanese 1000-Day Anniversary Unacquired Specific Summons (Paid-only Powerful Skill Character Guaranteed)",
    "limited_586": "Arena MVP Unacquired Specific Summons (Paid-Only Character Guaranteed)",
    "limited_587": "Subjugation MVP Unacquired Specific Summons (Paid-Only Character Guaranteed)",
    "limited_595": "End of the Year New Year Countdown Paid-Only Summons Vol. 1",
    "limited_596": "End of the Year New Year Countdown Paid-Only Summons Vol. 2",
    "limited_589": "New Year's Resurrected Festive Character Paid-Only Guaranteed Summons Vol. 1",
    "limited_590": "New Year's Resurrected Festive Character Paid-Only Guaranteed Summons Vol. 2",
    **{f"limited_{n}": "Story Completion Countdown x10 Free per Day Summons" for n in (600, 601, 602, 603, 604, 605, 609, 610)},
    "limited_123": "Yuletide Wishes Limited-Time Summons", "step_up_503001": "Yuletide Wishes Paid Only: Multi-Step Summons",
    "limited_144": "Japanese 1st Anniversary 218+2 Free Summons",
}
UNDATED = "No date in the game data"
QUEST_CAMPAIGNS = {1: "Increased Drop Rate", 2: "Increased Drops", 3: "Half Stamina", 4: "Gold Up", 5: "Drop Bonus"}


def day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%-d %b %Y")


def month(ms: int) -> str:
    return datetime.fromtimestamp(max(ms, LAUNCH) / 1000, timezone.utc).strftime("%Y-%m")


def month_label(key: str) -> str:
    return datetime.strptime(key, "%Y-%m").strftime("%B %Y")


def span(start: int, end: int) -> dict:
    """A date range as the pages show it. Content from before global launch is there from launch and an
    end past the service is none. A start past it is the game data's placeholder (most are 19 Aug to
    16 Sep 2099): the row's real dates are not in the data, which does not mean it never ran."""
    if start >= FOREVER:
        label = "No date"
    elif end >= FOREVER:
        label = "From launch, no end" if start < LAUNCH else f"From {day(start)}, no end"
    else:
        label = f"{'Launch' if start < LAUNCH else day(start)} – {day(end)}"
    return {"start": start, "end": end, "label": label, "ran": start < FOREVER,
            "limited": start < FOREVER and end < FOREVER}


class Stored:
    """The Schedule's tabs as the index keeps them."""

    def __init__(self, tabs: dict):
        self.tabs = tabs

    def __getattr__(self, tab):
        if tab not in dict(TABS):
            raise AttributeError(tab)
        return lambda: self.tabs[tab]

    def find(self, tab: str, ident: int) -> dict | None:
        return next((i for g in self.tabs[tab] for i in g["items"] if i["id"] == ident), None)


class Schedule:
    """master(table) -> rows, text(prefix) -> {key: value}, has(path) -> whether assetbundle/<path> exists;
    costumes and companions are the assets the Archive has pages for."""

    def __init__(self, master, texts, has, weapon_names=None, costumes=(), companions=()):
        self.m, self.has = master, has
        self.t = defaultdict(dict)
        for prefix in ("gacha.title.", "quest.event.chapter_title.", "quest.name.", "shop.name.", "shop.item.name.",
                       "consumable_item.name.", "material.name.", "important_item.name.", "costume.name.",
                       "companion.name.", "parts.group.name.", "thought.name.", "loginbonus.title.", "pvp.season.name."):
            self.t[prefix] = texts(prefix)
        self.weapon_names = weapon_names or {}
        self.costumes, self.companions = set(costumes), set(companions)
        self.index = lambda table, key: {r[key]: r for r in self.m(table)}

    def text(self, prefix: str, key, default: str = "") -> str:
        value = self.t[prefix].get(prefix + str(key), "")
        return value if value and value != "-" else default

    def art(self, *paths) -> str:
        return next((p for p in paths if p and self.has(p)), "")

    # ---- Items ------------------------------------------------------------------
    def item(self, kind: int, ident: int, count: int = 1) -> dict:
        """A possession by type and id: its name, and a link when the Archive has a page for it."""
        name, link = "", ""
        asset = lambda row, prefix, skeleton="ActorSkeletonId": f"{prefix}{row[skeleton]:03d}{row['AssetVariationId']:03d}"
        key = lambda row: f"{row['AssetCategoryId']:03d}{row['AssetVariationId']:03d}"
        if kind in (1, 7):
            costume_id = self.costume_enhanced.get(ident, {}).get("CostumeId", ident) if kind == 7 else ident
            row = self.costume_rows.get(costume_id)
            if row:
                a = asset(row, "ch")
                name, link = self.text("costume.name.", a), f"/costume/{a}" if a in self.costumes else ""
        elif kind in (2, 8):
            row = self.weapons.get(ident)
            if row:
                name = self.weapon_names.get(asset(row, "wp" if row["WeaponCategoryType"] == 1 else "mw", "WeaponType"), "")
        elif kind in (3, 9):
            companion_id = self.companion_enhanced.get(ident, {}).get("CompanionId", ident) if kind == 9 else ident
            row = self.companion_rows.get(companion_id)
            if row:
                a = asset(row, "cm")
                name, link = self.text("companion.name.", a), f"/companion/{a}" if a in self.companions else ""
        elif kind in (4, 10):
            group = self.parts_groups.get(self.parts.get(ident, {}).get("PartsGroupId"), {})
            name = self.text("parts.group.name.", group.get("PartsGroupAssetId", 0))
        elif kind == 5 and ident in self.materials:
            name = self.text("material.name.", key(self.materials[ident]))
        elif kind == 6 and ident in self.consumables:
            name = self.text("consumable_item.name.", key(self.consumables[ident]))
        elif kind == 13 and ident in self.important:
            name = self.text("important_item.name.", key(self.important[ident]))
        elif kind == 14 and ident in self.thoughts:
            name = self.text("thought.name.", f"{self.thoughts[ident]['ThoughtAssetId']:06d}")
        elif kind in (11, 12):
            name = "Paid gems" if kind == 11 else "Gems"
        elif kind == 15:
            name = "Mission pass points"
        elif kind == 16:
            name = "Premium item"
        kinds = {1: "Costume", 2: "Weapon", 3: "Companion", 4: "Memoir", 5: "Material", 6: "Item", 7: "Costume",
                 8: "Weapon", 9: "Companion", 10: "Memoir", 13: "Key item", 14: "Debris"}
        return {"name": name or f"{kinds.get(kind, 'Item')} {ident}", "count": count, "link": link,
                "enhanced": kind in (7, 8, 9, 10)}

    def __getattr__(self, name):
        # Lookups built on first use: id -> row.
        tables = {"costume_rows": ("m_costume", "CostumeId"), "costume_enhanced": ("m_costume_enhanced", "CostumeEnhancedId"),
                  "companion_rows": ("m_companion", "CompanionId"), "companion_enhanced": ("m_companion_enhanced", "CompanionEnhancedId"),
                  "weapons": ("m_weapon", "WeaponId"), "parts": ("m_parts", "PartsId"), "parts_groups": ("m_parts_group", "PartsGroupId"),
                  "materials": ("m_material", "MaterialId"), "consumables": ("m_consumable_item", "ConsumableItemId"),
                  "important": ("m_important_item", "ImportantItemId"), "thoughts": ("m_thought", "ThoughtId"),
                  "shops_by_id": ("m_shop", "ShopId"), "shop_items": ("m_shop_item", "ShopItemId"),
                  "stocks": ("m_shop_item_limited_stock", "ShopItemLimitedStockId"),
                  "cell_terms": ("m_shop_item_cell_term", "ShopItemCellTermId"), "quests": ("m_quest", "QuestId")}
        if name not in tables:
            raise AttributeError(name)
        value = self.index(*tables[name])
        setattr(self, name, value)
        return value

    def price(self, item: dict) -> str:
        """Price type 1 is an item (PriceId names it), 2 gems, 4 real money."""
        if item["PriceType"] == 1:
            return "Free" if not item["Price"] else f"{item['Price']:,} × {self.item(6, item['PriceId'])['name']}"
        return {2: f"{item['Price']:,} gems", 4: "Real-money purchase"}.get(item["PriceType"], "")

    # ---- Shops ------------------------------------------------------------------
    def shop_lineup(self, shop: dict) -> list[dict]:
        cells = {r["ShopItemCellId"]: r for r in self.m("m_shop_item_cell")}
        contents = defaultdict(list)
        for r in self.m("m_shop_item_content_possession"):
            contents[r["ShopItemId"]].append(r)
        out = []
        for g in sorted((r for r in self.m("m_shop_item_cell_group") if r["ShopItemCellGroupId"] == shop["ShopItemCellGroupId"]),
                        key=lambda r: r["SortOrder"]):
            cell = cells.get(g["ShopItemCellId"])
            item = self.shop_items.get(cell["ShopItemId"]) if cell else None
            if not item:
                continue
            stock = self.stocks.get(item["ShopItemLimitedStockId"], {}).get("MaxCount", 0)
            term = self.cell_terms.get(g["ShopItemCellTermId"])
            gets = [self.item(r["PossessionType"], r["PossessionId"], r["Count"])
                    for r in sorted(contents[item["ShopItemId"]], key=lambda r: r["SortOrder"])]
            out.append({"name": self.text("shop.item.name.", item["NameShopTextId"]) or (gets[0]["name"] if gets else f"Item {item['ShopItemId']}"),
                        "price": self.price(item), "limit": stock, "step": cell["StepNumber"], "gets": gets,
                        "term": span(term["StartDatetime"], term["EndDatetime"])["label"] if term else ""})
        return out

    def shop_name(self, shop: dict) -> str:
        return self.text("shop.name.", shop["NameShopTextId"], f"Shop {shop['ShopId']}")

    @memo
    def shops(self) -> list[dict]:
        """Every shop that ran for a time, by the month it opened."""
        months = defaultdict(list)
        for shop in sorted(self.m("m_shop"), key=lambda r: (r["StartDatetime"], r["ShopId"])):
            when = span(shop["StartDatetime"], shop["EndDatetime"])
            months[month(shop["StartDatetime"]) if when["limited"] else "always" if when["ran"] else "never"].append(
                {"id": shop["ShopId"], "name": self.shop_name(shop), "kind": SHOP_TYPES.get(shop["ShopType"], "Shop"),
                 "when": when, "items": self.shop_lineup(shop)})
        labels = {"always": "Always open", "never": UNDATED}
        return [{"key": k, "label": labels.get(k) or month_label(k), "items": v}
                for k, v in sorted(months.items(), key=lambda kv: (kv[0] in labels, kv[0] == "never", kv[0]))]

    # ---- Summons ----------------------------------------------------------------
    def summon_title(self, gacha: int, asset: str) -> str:
        for key in (asset, f"limited_{gacha}", f"limited_{gacha:02d}"):
            if key and self.text("gacha.title.", key):
                return self.text("gacha.title.", key)
        return ART_TITLES.get(asset, "")

    @memo
    def summons(self) -> list[dict]:
        """Every summon on a home banner, plus summons with shards but no banner, by the month they first ran."""
        runs = defaultdict(list)
        for b in self.m("m_mom_banner"):
            if b["DestinationDomainType"] == 1:
                runs[b["DestinationDomainId"]].append(b)
        medals = {r["ShopTransitionGachaId"]: r for r in self.m("m_gacha_medal")}
        by_item = {r["ConsumableItemId"]: r for r in self.m("m_gacha_medal")}
        for gacha, owner in SHARED_MEDALS.items():
            if owner in medals:
                medals.setdefault(gacha, medals[owner])
        for gacha, item in MEDAL_ITEMS.items():
            if item in by_item:
                medals.setdefault(gacha, by_item[item])
        sells = defaultdict(list)  # shard item -> exchange shops
        items_by_cell_group = defaultdict(set)
        cells = {r["ShopItemCellId"]: r["ShopItemId"] for r in self.m("m_shop_item_cell")}
        for g in self.m("m_shop_item_cell_group"):
            item = self.shop_items.get(cells.get(g["ShopItemCellId"]))
            if item and item["PriceType"] == 1:
                items_by_cell_group[g["ShopItemCellGroupId"]].add(item["PriceId"])
        for shop in self.m("m_shop"):
            for price in items_by_cell_group[shop["ShopItemCellGroupId"]]:
                sells[price].append(shop)
        found = []
        for gacha in sorted(set(runs) | set(medals)):
            banners = sorted(runs.get(gacha, []), key=lambda b: b["StartDatetime"])
            asset = next((b["BannerAssetName"] for b in banners if b["BannerAssetName"]), "")
            medal = medals.get(gacha)
            shard = self.item(6, medal["ConsumableItemId"])["name"] if medal else ""
            title = self.summon_title(gacha, asset)
            if not title and shard:
                label = shard[shard.find("(") + 1:shard.rfind(")")] if "(" in shard else shard.removesuffix(" Medal")
                title = label if "summon" in label.lower() else f"{label} Summons"
            shops = sorted(sells.get(medal["ConsumableItemId"], []) if medal else [], key=lambda s: s["StartDatetime"])
            dated = [span(b["StartDatetime"], b["EndDatetime"]) for b in banners]
            # No banner, or only placeholder rows: the shard's exchange shop dates the summon, as on the
            # server (bannerlessSummons, parkedReruns): from its opening to two days before the shards convert.
            exchange = bool(shops) and not any(d["ran"] for d in dated) and medal["AutoConvertDatetime"] < FOREVER \
                and shops[0]["StartDatetime"] < medal["AutoConvertDatetime"]
            if exchange:
                dated.insert(0, span(shops[0]["StartDatetime"], medal["AutoConvertDatetime"] - 2 * DAY))
            first = min((d["start"] for d in dated), default=FOREVER)
            # mom_banner is the home-screen banner (cards), banner the summon screen's (the summon's page).
            art = self.art(f"ui/gacha/en/{asset}/mom_banner.assetbundle", f"ui/gacha/en/{asset}/banner.assetbundle") if asset else ""
            hero = self.art(f"ui/gacha/en/{asset}/banner.assetbundle") or art if asset else ""
            found.append({
                "id": gacha, "title": title or f"Summon {gacha}" + (" (Japanese files only)" if asset and self.has(f"ui/gacha/ja/{asset}/mom_banner.assetbundle") else ""), "asset": asset, "banner": not banners,
                "art": art, "hero": hero, "english": bool(art or self.summon_title(gacha, asset)), "exchange": exchange,
                "ran": first < FOREVER,
                "runs": ([{"banner": 0, **dated[0]}] if exchange else []) + [{"banner": b["MomBannerId"], **d} for b, d in zip(banners, dated[exchange:])],
                "first": first,
                "medal": {"shard": shard, "ceiling": medal["CeilingCount"], "converts": day(medal["AutoConvertDatetime"])
                          if medal["AutoConvertDatetime"] < FOREVER else "", "id": medal["GachaMedalId"]} if medal else None,
                "shops": [{"id": s["ShopId"], "name": self.shop_name(s), "when": span(s["StartDatetime"], s["EndDatetime"]),
                           "items": self.shop_lineup(s)} for s in shops],
            })
        return self.by_month(found, "first")

    def by_month(self, items: list[dict], field: str) -> list[dict]:
        months = defaultdict(list)
        for it in sorted(items, key=lambda i: (i[field], i["id"])):
            months[month(it[field]) if it[field] < FOREVER else "never"].append(it)
        return [{"key": k, "label": UNDATED if k == "never" else month_label(k), "items": v}
                for k, v in sorted(months.items(), key=lambda kv: (kv[0] == "never", kv[0]))]

    # ---- Events -----------------------------------------------------------------
    @memo
    def events(self) -> list[dict]:
        """Event chapters by type, each with its quests by difficulty."""
        groups = defaultdict(list)
        for r in self.m("m_event_quest_sequence_group"):
            groups[r["EventQuestSequenceGroupId"]].append(r)
        sequences = defaultdict(list)
        for r in self.m("m_event_quest_sequence"):
            sequences[r["EventQuestSequenceId"]].append(r)
        seasons = defaultdict(list)
        for r in self.m("m_event_quest_labyrinth_season"):
            seasons[r["EventQuestChapterId"]].append(span(r["StartDatetime"], r["EndDatetime"]) | {"number": r["SeasonNumber"]})
        difficulty = {1: "Normal", 2: "Hard", 3: "Very Hard"}
        kinds = defaultdict(list)
        for c in sorted(self.m("m_event_quest_chapter"), key=lambda r: (r["StartDatetime"], r["DisplaySortOrder"], r["EventQuestChapterId"])):
            ident = c["EventQuestChapterId"]
            levels = []
            for g in sorted(groups[c["EventQuestSequenceGroupId"]], key=lambda r: r["DifficultyType"]):
                quests = []
                for s in sorted(sequences[g["EventQuestSequenceId"]], key=lambda r: r["SortOrder"]):
                    q = self.quests.get(s["QuestId"], {})
                    quests.append(self.text("quest.name.", q.get("NameQuestTextId", 0)) or f"Quest {s['QuestId']}")
                levels.append({"name": difficulty.get(g["DifficultyType"], f"Difficulty {g['DifficultyType']}"), "quests": quests})
            kind = EVENT_TYPES.get(c["EventQuestType"], f"Type {c['EventQuestType']}")
            title = self.text("quest.event.chapter_title.", ident) or (levels[0]["quests"][0] if levels and levels[0]["quests"] else f"{kind} {ident}")
            banner = c["BannerAssetId"]
            kinds[kind].append({"id": ident, "title": title, "kind": kind, "when": span(c["StartDatetime"], c["EndDatetime"]),
                                "art": self.art(f"ui/quest/en/banner/event_banner_{banner:03d}.assetbundle",
                                                f"ui/quest/en/list_banner/event_list_banner_{banner}.assetbundle") if banner else "",
                                "levels": levels, "seasons": seasons.get(ident, [])})
        order = list(dict.fromkeys(EVENT_TYPES.values()))
        return [{"key": k, "label": k, "items": v} for k, v in sorted(kinds.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)]

    # ---- Home banners -----------------------------------------------------------
    @memo
    def banners(self) -> list[dict]:
        summon_titles = {s["id"]: s["title"] for m in self.summons() for s in m["items"]}
        found = []
        # A placeholder row whose target also has a dated row: a second banner for something that ran.
        dated = {(b["DestinationDomainType"], b["DestinationDomainId"]) for b in self.m("m_mom_banner") if b["StartDatetime"] < FOREVER}
        for b in self.m("m_mom_banner"):
            kind, target = b["DestinationDomainType"], b["DestinationDomainId"]
            name = ""
            if kind == 1:
                name = summon_titles.get(target, "")
            elif kind == 2 and target in self.shops_by_id:
                name = self.shop_name(self.shops_by_id[target])
            asset = b["BannerAssetName"]
            art = self.art(f"ui/gacha/en/{asset}/mom_banner.assetbundle", f"ui/gacha/en/{asset}/banner.assetbundle") if kind == 1 \
                else self.art(f"ui/mom_banner/en/mom_banner_{asset}.assetbundle") if asset else ""
            found.append({"id": b["MomBannerId"], "first": b["StartDatetime"], "kind": BANNER_TARGETS.get(kind, f"Type {kind}"),
                          "target": target, "name": name, "asset": asset, "art": art, "when": span(b["StartDatetime"], b["EndDatetime"]),
                          "also": b["StartDatetime"] >= FOREVER and (kind, target) in dated})
        return self.by_month(found, "first")

    # ---- Other ------------------------------------------------------------------
    @memo
    def other(self) -> list[dict]:
        sections = []
        login = []
        for r in sorted(self.m("m_login_bonus"), key=lambda r: r["StartDatetime"]):
            asset = r["LoginBonusAssetName"]
            login.append({"id": r["LoginBonusId"], "title": self.text("loginbonus.title.", asset, f"Login bonus {r['LoginBonusId']}"),
                          "when": span(r["StartDatetime"], r["EndDatetime"]), "art": self.art(f"ui/login_bonus/en/banner/{asset}.assetbundle")})
        sections.append({"key": "login", "label": "Login bonuses", "items": login})
        sections.append({"key": "arena", "label": "Arena seasons", "items": [
            {"id": r["PvpSeasonId"], "title": self.text("pvp.season.name.", f"{r['PvpSeasonId'] % 1000:03d}", f"Season {r['PvpSeasonId'] % 1000:03d}"),
             "when": span(r["SeasonStartDatetime"], r["SeasonEndDatetime"])}
            for r in sorted(self.m("m_pvp_season"), key=lambda r: r["SeasonStartDatetime"]) if not r["IsInvalid"]]})
        sections.append({"key": "hunt", "label": "Subjugation Battles", "items": [
            {"id": r["BigHuntScheduleId"], "title": f"Subjugation Battle {r['BigHuntScheduleId']}", "when": span(r["ChallengeStartDatetime"], r["ChallengeEndDatetime"])}
            for r in sorted(self.m("m_big_hunt_schedule"), key=lambda r: r["ChallengeStartDatetime"])]})
        sections.append({"key": "pass", "label": "Mission pass", "items": [
            {"id": r["MissionPassId"], "title": f"Mission pass {i}", "when": span(r["StartDatetime"], r["EndDatetime"])}
            for i, r in enumerate(sorted(self.m("m_mission_pass"), key=lambda r: r["StartDatetime"]), 1)]})
        effects = defaultdict(list)
        for r in self.m("m_quest_campaign_effect_group"):
            effects[r["QuestCampaignEffectGroupId"]].append(r)
        campaigns = []
        for r in self.m("m_quest_campaign"):
            parts = [f"{QUEST_CAMPAIGNS.get(e['QuestCampaignEffectType'], 'Bonus')} ×{e['QuestCampaignEffectValue'] / 100:g}"
                     if e["QuestCampaignEffectType"] in (1, 2) else QUEST_CAMPAIGNS.get(e["QuestCampaignEffectType"], "Bonus")
                     for e in effects[r["QuestCampaignEffectGroupId"]]]
            campaigns.append({"id": r["QuestCampaignId"], "title": "Quest campaign: " + (", ".join(dict.fromkeys(parts)) or "bonus"),
                              "when": span(r["StartDatetime"], r["EndDatetime"])})
        for r in self.m("m_enhance_campaign"):
            effect = "Glorious success rate up" if r["EnhanceCampaignEffectType"] == 2 else "Enhancement bonus"
            campaigns.append({"id": r["EnhanceCampaignId"], "title": effect,
                              "when": span(r["StartDatetime"], r["EndDatetime"])})
        sections.append({"key": "campaigns", "label": "Campaigns", "items": sorted(campaigns, key=lambda c: c["when"]["start"])})
        sections.append({"key": "fortune", "label": "Fortune draws", "items": [
            {"id": r["OmikujiId"], "title": f"Fortune draw {r['OmikujiId']}", "when": span(r["StartDatetime"], r["EndDatetime"])}
            for r in sorted(self.m("m_omikuji"), key=lambda r: r["StartDatetime"])]})
        sections.append({"key": "comeback", "label": "Welcome back campaigns", "items": [
            {"id": r["ComebackCampaignId"], "title": f"Away {r['ComebackJudgeDayCount']} days: {r['GrantCampaignTermDayCount']} days of rewards",
             "when": span(r["ComebackJudgeStartDatetime"], r["ComebackJudgeEndDatetime"])}
            for r in sorted(self.m("m_comeback_campaign"), key=lambda r: r["ComebackJudgeStartDatetime"])]})
        for s in sections:
            ran = [i for i in s["items"] if i["when"]["ran"]]
            s["hidden"] = len(s["items"]) - len(ran)
            s["items"] = ran
        return sections

    def find(self, tab: str, ident: int) -> dict | None:
        """One summon, event or shop by id."""
        return next((i for g in getattr(self, tab)() for i in g["items"] if i["id"] == ident), None)

    # ---- Timeline ---------------------------------------------------------------
    @memo
    def timeline(self) -> list[dict]:
        """What started each month, across every tab, linked to its entry."""
        entries = []
        for m in self.summons():
            for s in m["items"]:
                for r in s["runs"]:
                    if r["limited"]:
                        entries.append((r["start"], "Summon", s["title"], r["label"], f"/schedule?tab=summons#summon-{s['id']}"))
        for k in self.events():
            for e in k["items"]:
                if e["when"]["limited"]:
                    entries.append((e["when"]["start"], e["kind"], e["title"], e["when"]["label"], f"/schedule?tab=events#event-{e['id']}"))
                for season in e["seasons"]:
                    if season["limited"]:
                        entries.append((season["start"], e["kind"], f"{e['title']}, season {season['number']}", season["label"],
                                        f"/schedule?tab=events#event-{e['id']}"))
        for m in self.shops():
            for s in m["items"]:
                if s["when"]["limited"] and s["kind"] != "Exchange":
                    entries.append((s["when"]["start"], s["kind"], s["name"], s["when"]["label"], f"/schedule?tab=shops#shop-{s['id']}"))
        for section in self.other():
            if section["key"] in ("campaigns",):
                continue
            for i in section["items"]:
                if i["when"]["limited"]:
                    entries.append((i["when"]["start"], section["label"], i["title"], i["when"]["label"], f"/schedule?tab=other#{section['key']}"))
        months = defaultdict(list)
        for start, kind, title, label, link in sorted(entries, key=lambda e: (e[0], e[1], e[2])):
            months[month(start)].append({"kind": kind, "title": title, "label": label, "link": link})
        return [{"key": k, "label": month_label(k), "items": v} for k, v in sorted(months.items())]
