"""The live service's dated content for the Archive's Schedule pages: summons, events, shops, home
banners and the rest, with their original dates from the master data.

The index keeps the Schedule it works out, so its words are references (words.t) that Stored puts in the
language chosen when a page reads them."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .memo import memo
from .words import resolve, t, t_count

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

TABS = (("timeline", t("archive.schedule.timeline")), ("summons", t("archive.schedule.summons")),
        ("events", t("archive.schedule.events")), ("shops", t("archive.schedule.shops")),
        ("banners", t("archive.schedule.banners")), ("other", t("archive.schedule.other")))
EVENT_TYPES = {1: t("archive.schedule.record"), 2: t("archive.schedule.variation"), 3: t("archive.schedule.remnant"),
               4: t("archive.schedule.daily"), 5: t("archive.schedule.guerrilla"), 6: t("archive.schedule.character_quest"),
               7: t("archive.schedule.character_quest"), 8: t("archive.schedule.hidden"), 9: t("archive.schedule.special"),
               10: t("archive.schedule.abyss_tower"), 11: t("archive.schedule.chambers_of_dusk"),
               12: t("archive.schedule.fate_board")}
SHOP_TYPES = {1: t("archive.schedule.gems"), 3: t("archive.schedule.item_shop"), 4: t("archive.schedule.exchange"),
              5: t("archive.schedule.recovery"), 6: t("archive.schedule.recovery"), 7: t("archive.schedule.packs"),
              9: t("archive.schedule.mission_packs"), 10: t("archive.schedule.mamas_choice"),
              11: t("archive.schedule.monthly_pass")}
SUMMON, SHOP = 1, 2  # home banner targets with a page in the Archive
BANNER_TARGETS = {SUMMON: t("archive.schedule.summon"), SHOP: t("archive.schedule.shop"), 21: t("archive.schedule.link"),
                  22: t("archive.schedule.missions"), 23: t("archive.schedule.announcement"),
                  27: t("archive.schedule.panel_mission")}
# The server's medal links (server/internal/masterdata/gacha.go): summons sharing another summon's
# medal, and summons whose medal is known only by its shard item.
SHARED_MEDALS = {46: 45, 151: 150}
MEDAL_ITEMS = {401: 8087, 501: 8168, 535: 8192, 541: 8192, 542: 8192, 543: 8193, 549: 8197, 550: 8197,
               555: 8203, 556: 8203, 582: 8222, 583: 8222, 585: 8222, 510001: 8030, 513001: 8033,
               515001: 8045, 536001: 8110, 537001: 8133, 9000035: 8021}
# Summon titles where the game text is wrong (limited_416 and limited_417's are swapped,
# limited_428's names the summon a month later) or Japanese only ("fixed"), and summons whose title is
# drawn into the banner art only, read from ui/gacha/en/<asset>/mom_banner ("art"). Keyed by banner
# asset; the server's summon_rules.json "titles" holds the fixed list. Game content: summon_titles.json.
_TITLES = json.loads(Path(__file__).with_name("summon_titles.json").read_text(encoding="utf-8"))
FIXED_TITLES, ART_TITLES = _TITLES["fixed"], _TITLES["art"]
UNDATED = t("archive.schedule.undated")
# Words that go inside other texts ("Quest 12", "Launch – 8 Sep 2021").
ITEM, SHOP_WORD, SUMMON_WORD = t("archive.schedule.item"), t("archive.schedule.shop"), t("archive.schedule.summon")
QUEST, DIFFICULTY, TYPE = t("archive.schedule.quest"), t("archive.schedule.difficulty"), t("archive.schedule.type")
LAUNCH_DAY = t("archive.schedule.launch")
QUEST_CAMPAIGNS = {1: t("archive.schedule.increased_drop_rate"), 2: t("archive.schedule.increased_drops"),
                   3: t("archive.schedule.half_stamina"), 4: t("archive.schedule.gold_up"), 5: t("archive.schedule.drop_bonus")}


def _month_name(number: int, short: bool) -> str:
    if short:
        return (t("common.month_short.jan"), t("common.month_short.feb"), t("common.month_short.mar"), t("common.month_short.apr"),
                t("common.month_short.may"), t("common.month_short.jun"), t("common.month_short.jul"), t("common.month_short.aug"),
                t("common.month_short.sep"), t("common.month_short.oct"), t("common.month_short.nov"), t("common.month_short.dec"))[number - 1]
    return (t("archive.date.january"), t("archive.date.february"), t("archive.date.march"), t("archive.date.april"),
            t("archive.date.may"), t("archive.date.june"), t("archive.date.july"), t("archive.date.august"),
            t("archive.date.september"), t("archive.date.october"), t("archive.date.november"),
            t("archive.date.december"))[number - 1]


def day(ms: int) -> str:
    """A day (a reference: 28 Jul 2021)."""
    at = datetime.fromtimestamp(ms / 1000, timezone.utc)
    return t("archive.date.day", day=at.day, month=_month_name(at.month, True), year=at.year)


def month(ms: int) -> str:
    return datetime.fromtimestamp(max(ms, LAUNCH) / 1000, timezone.utc).strftime("%Y-%m")


def month_label(key: str) -> str:
    """A month (a reference: July 2021)."""
    at = datetime.strptime(key, "%Y-%m")
    return t("archive.date.month", month=_month_name(at.month, False), year=at.year)


def month_short(ms: int) -> str:
    """A month, short (a reference: Jul 2021)."""
    at = datetime.fromtimestamp(ms / 1000, timezone.utc)
    return t("archive.date.month", month=_month_name(at.month, True), year=at.year)


def when(start: int, end: int) -> dict:
    """A date range as the pages show it, its label a reference. Content from before global launch is there
    from launch and an end past the service is none. A start past it is the game data's placeholder (most
    are 19 Aug to 16 Sep 2099): the row's real dates are not in the data, which does not mean it never ran."""
    if start >= FOREVER:
        label = t("archive.schedule.no_date")
    elif end >= FOREVER:
        label = t("archive.schedule.from_launch_no_end") if start < LAUNCH else t("archive.schedule.from_no_end", start=day(start))
    else:
        label = t("archive.schedule.range", start=LAUNCH_DAY if start < LAUNCH else day(start), end=day(end))
    return {"start": start, "end": end, "label": label, "ran": start < FOREVER,
            "limited": start < FOREVER and end < FOREVER}


def away(days: int, rewards: int) -> str:
    """A welcome back campaign (a reference: Away 30 days: 7 days of rewards)."""
    gone, given = t_count("archive.schedule.away_days", days), t_count("archive.schedule.reward_days", rewards)
    return t("archive.schedule.away", away=gone, rewards=given)


def span(start: int, end: int) -> dict:
    """when(), in words."""
    return resolve(when(start, end))


class Stored:
    """The Schedule's tabs as the index keeps them, in words when read."""

    def __init__(self, tabs: dict):
        self.tabs = tabs

    def __getattr__(self, tab):
        if tab not in dict(TABS):
            raise AttributeError(tab)
        return lambda: resolve(self.tabs[tab])

    def find(self, tab: str, ident: int) -> dict | None:
        return resolve(next((i for g in self.tabs[tab] for i in g["items"] if i["id"] == ident), None))

    @classmethod
    def worked_out(cls, schedule: "Schedule") -> "Stored":
        """Every tab of a Schedule, as the index keeps them."""
        return cls({tab: getattr(schedule, tab)() for tab, _ in TABS})


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
            name = t("archive.schedule.paid_gems") if kind == 11 else t("archive.schedule.gems")
        elif kind == 15:
            name = t("archive.schedule.mission_pass_points")
        elif kind == 16:
            name = t("archive.schedule.premium_item")
        kinds = {1: t("archive.schedule.costume"), 2: t("archive.schedule.weapon"), 3: t("archive.schedule.companion"),
                 4: t("archive.schedule.memoir"), 5: t("archive.schedule.material"), 6: t("archive.schedule.item"),
                 7: t("archive.schedule.costume"), 8: t("archive.schedule.weapon"), 9: t("archive.schedule.companion"),
                 10: t("archive.schedule.memoir"), 13: t("archive.schedule.key_item"), 14: t("archive.schedule.debris")}
        return {"name": name or t("archive.schedule.numbered", kind=kinds.get(kind, ITEM), n=ident),
                "count": count, "link": link,
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
            return t("archive.schedule.free") if not item["Price"] else \
                t("archive.schedule.price_items", count=f"{item['Price']:,}", item=self.item(6, item["PriceId"])["name"])
        if item["PriceType"] == 2:
            return t_count("archive.schedule.price_gems", item["Price"], count=f"{item['Price']:,}")
        return t("archive.schedule.real_money") if item["PriceType"] == 4 else ""

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
            out.append({"name": self.text("shop.item.name.", item["NameShopTextId"]) or (gets[0]["name"] if gets else t("archive.schedule.numbered", kind=ITEM, n=item["ShopItemId"])),
                        "price": self.price(item), "limit": stock, "step": cell["StepNumber"], "gets": gets,
                        "term": when(term["StartDatetime"], term["EndDatetime"])["label"] if term else ""})
        return out

    def shop_name(self, shop: dict) -> str:
        return self.text("shop.name.", shop["NameShopTextId"]) or t("archive.schedule.numbered", kind=SHOP_WORD, n=shop["ShopId"])

    @memo
    def shops(self) -> list[dict]:
        """Every shop that ran for a time, by the month it opened."""
        months = defaultdict(list)
        for shop in sorted(self.m("m_shop"), key=lambda r: (r["StartDatetime"], r["ShopId"])):
            dates = when(shop["StartDatetime"], shop["EndDatetime"])
            months[month(shop["StartDatetime"]) if dates["limited"] else "always" if dates["ran"] else "never"].append(
                {"id": shop["ShopId"], "name": self.shop_name(shop), "kind": SHOP_TYPES.get(shop["ShopType"], t("archive.schedule.shop")),
                 "type": shop["ShopType"], "when": dates, "items": self.shop_lineup(shop)})
        labels = {"always": t("archive.schedule.always_open"), "never": UNDATED}
        return [{"key": k, "label": labels.get(k) or month_label(k), "items": v}
                for k, v in sorted(months.items(), key=lambda kv: (kv[0] in labels, kv[0] == "never", kv[0]))]

    # ---- Summons ----------------------------------------------------------------
    def summon_title(self, gacha: int, asset: str) -> str:
        if asset in FIXED_TITLES:
            return FIXED_TITLES[asset]
        for key in (asset, f"limited_{gacha}", f"limited_{gacha:02d}"):
            if key and self.text("gacha.title.", key):
                return self.text("gacha.title.", key)
        return ART_TITLES.get(asset, "")

    @memo
    def summons(self) -> list[dict]:
        """Every summon on a home banner, plus summons with shards but no banner, by the month they first ran."""
        runs = defaultdict(list)
        for b in self.m("m_mom_banner"):
            if b["DestinationDomainType"] == SUMMON:
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
                label = shard[shard.find("(") + 1:shard.rfind(")")] if "(" in shard else re.sub(r" Medal$", "", shard)
                title = label if "summon" in label.lower() else t("archive.schedule.summons_named", name=label)
            shops = sorted(sells.get(medal["ConsumableItemId"], []) if medal else [], key=lambda s: s["StartDatetime"])
            dated = [when(b["StartDatetime"], b["EndDatetime"]) for b in banners]
            # No banner, or only placeholder rows: the shard's exchange shop dates the summon, as on the
            # server (bannerlessSummons, parkedReruns): from its opening to two days before the shards convert.
            exchange = bool(shops) and not any(d["ran"] for d in dated) and medal["AutoConvertDatetime"] < FOREVER \
                and shops[0]["StartDatetime"] < medal["AutoConvertDatetime"]
            if exchange:
                dated.insert(0, when(shops[0]["StartDatetime"], medal["AutoConvertDatetime"] - 2 * DAY))
            first = min((d["start"] for d in dated), default=FOREVER)
            # mom_banner is the home-screen banner (cards), banner the summon screen's (the summon's page).
            art = self.art(f"ui/gacha/en/{asset}/mom_banner.assetbundle", f"ui/gacha/en/{asset}/banner.assetbundle") if asset else ""
            hero = self.art(f"ui/gacha/en/{asset}/banner.assetbundle") or art if asset else ""
            found.append({
                "id": gacha, "title": title or (t("archive.schedule.summon_japanese_only", n=gacha) if asset and self.has(f"ui/gacha/ja/{asset}/mom_banner.assetbundle")
                                   else t("archive.schedule.numbered", kind=SUMMON_WORD, n=gacha)), "asset": asset, "banner": not banners,
                "art": art, "hero": hero, "english": bool(art or self.summon_title(gacha, asset)), "exchange": exchange,
                "ran": first < FOREVER,
                "runs": ([{"banner": 0, **dated[0]}] if exchange else []) + [{"banner": b["MomBannerId"], **d} for b, d in zip(banners, dated[exchange:])],
                "first": first,
                "medal": {"shard": shard, "ceiling": medal["CeilingCount"], "converts": day(medal["AutoConvertDatetime"])
                          if medal["AutoConvertDatetime"] < FOREVER else "", "id": medal["GachaMedalId"]} if medal else None,
                "shops": [{"id": s["ShopId"], "name": self.shop_name(s), "when": when(s["StartDatetime"], s["EndDatetime"]),
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
            seasons[r["EventQuestChapterId"]].append(when(r["StartDatetime"], r["EndDatetime"]) | {"number": r["SeasonNumber"]})
        difficulty = {1: t("archive.schedule.normal"), 2: t("archive.schedule.hard"), 3: t("archive.schedule.very_hard")}
        kinds = defaultdict(list)
        for c in sorted(self.m("m_event_quest_chapter"), key=lambda r: (r["StartDatetime"], r["DisplaySortOrder"], r["EventQuestChapterId"])):
            ident = c["EventQuestChapterId"]
            levels = []
            for g in sorted(groups[c["EventQuestSequenceGroupId"]], key=lambda r: r["DifficultyType"]):
                quests = []
                for s in sorted(sequences[g["EventQuestSequenceId"]], key=lambda r: r["SortOrder"]):
                    q = self.quests.get(s["QuestId"], {})
                    quests.append(self.text("quest.name.", q.get("NameQuestTextId", 0)) or t("archive.schedule.numbered", kind=QUEST, n=s["QuestId"]))
                levels.append({"name": difficulty.get(g["DifficultyType"]) or t("archive.schedule.numbered", kind=DIFFICULTY, n=g["DifficultyType"]), "quests": quests})
            kind = EVENT_TYPES.get(c["EventQuestType"]) or t("archive.schedule.numbered", kind=TYPE, n=c["EventQuestType"])
            title = self.text("quest.event.chapter_title.", ident) or (levels[0]["quests"][0] if levels and levels[0]["quests"] else t("archive.schedule.numbered", kind=kind, n=ident))
            banner = c["BannerAssetId"]
            kinds[kind].append({"id": ident, "title": title, "kind": kind, "when": when(c["StartDatetime"], c["EndDatetime"]),
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
            if kind == SUMMON:
                name = summon_titles.get(target, "")
            elif kind == SHOP and target in self.shops_by_id:
                name = self.shop_name(self.shops_by_id[target])
            asset = b["BannerAssetName"]
            art = self.art(f"ui/gacha/en/{asset}/mom_banner.assetbundle", f"ui/gacha/en/{asset}/banner.assetbundle") if kind == SUMMON \
                else self.art(f"ui/mom_banner/en/mom_banner_{asset}.assetbundle") if asset else ""
            found.append({"id": b["MomBannerId"], "first": b["StartDatetime"], "kind": BANNER_TARGETS.get(kind) or t("archive.schedule.numbered", kind=TYPE, n=kind),
                          "domain": kind, "target": target, "name": name, "asset": asset, "art": art, "when": when(b["StartDatetime"], b["EndDatetime"]),
                          "also": b["StartDatetime"] >= FOREVER and (kind, target) in dated})
        return self.by_month(found, "first")

    # ---- Other ------------------------------------------------------------------
    @memo
    def other(self) -> list[dict]:
        sections = []
        login = []
        for r in sorted(self.m("m_login_bonus"), key=lambda r: r["StartDatetime"]):
            asset = r["LoginBonusAssetName"]
            login.append({"id": r["LoginBonusId"], "title": self.text("loginbonus.title.", asset) or t("archive.schedule.login_bonus", n=r["LoginBonusId"]),
                          "when": when(r["StartDatetime"], r["EndDatetime"]), "art": self.art(f"ui/login_bonus/en/banner/{asset}.assetbundle")})
        sections.append({"key": "login", "label": t("archive.schedule.login_bonuses"), "items": login})
        sections.append({"key": "arena", "label": t("archive.schedule.arena_seasons"), "items": [
            {"id": r["PvpSeasonId"], "title": self.text("pvp.season.name.", f"{r['PvpSeasonId'] % 1000:03d}") or t("archive.schedule.season", n=f"{r['PvpSeasonId'] % 1000:03d}"),
             "when": when(r["SeasonStartDatetime"], r["SeasonEndDatetime"])}
            for r in sorted(self.m("m_pvp_season"), key=lambda r: r["SeasonStartDatetime"]) if not r["IsInvalid"]]})
        sections.append({"key": "hunt", "label": t("archive.schedule.subjugation_battles"), "items": [
            {"id": r["BigHuntScheduleId"], "title": t("archive.schedule.subjugation_battle", n=r["BigHuntScheduleId"]), "when": when(r["ChallengeStartDatetime"], r["ChallengeEndDatetime"])}
            for r in sorted(self.m("m_big_hunt_schedule"), key=lambda r: r["ChallengeStartDatetime"])]})
        sections.append({"key": "pass", "label": t("archive.schedule.mission_pass"), "items": [
            {"id": r["MissionPassId"], "title": t("archive.schedule.mission_pass_numbered", n=i), "when": when(r["StartDatetime"], r["EndDatetime"])}
            for i, r in enumerate(sorted(self.m("m_mission_pass"), key=lambda r: r["StartDatetime"]), 1)]})
        effects = defaultdict(list)
        for r in self.m("m_quest_campaign_effect_group"):
            effects[r["QuestCampaignEffectGroupId"]].append(r)
        campaigns = []
        for r in self.m("m_quest_campaign"):
            effect = lambda e: QUEST_CAMPAIGNS.get(e["QuestCampaignEffectType"]) or t("archive.schedule.bonus")
            parts = [t("archive.schedule.rate", effect=effect(e), rate=f"{e['QuestCampaignEffectValue'] / 100:g}")
                     if e["QuestCampaignEffectType"] in (1, 2) else effect(e)
                     for e in effects[r["QuestCampaignEffectGroupId"]]]
            effects_named = t("archive.schedule.list_separator").join(dict.fromkeys(parts))
            campaigns.append({"id": r["QuestCampaignId"],
                              "title": t("archive.schedule.quest_campaign", effects=effects_named) if parts else t("archive.schedule.quest_campaign_bonus"),
                              "when": when(r["StartDatetime"], r["EndDatetime"])})
        for r in self.m("m_enhance_campaign"):
            title = t("archive.schedule.glorious_success") if r["EnhanceCampaignEffectType"] == 2 else t("archive.schedule.enhancement_bonus")
            campaigns.append({"id": r["EnhanceCampaignId"], "title": title,
                              "when": when(r["StartDatetime"], r["EndDatetime"])})
        sections.append({"key": "campaigns", "label": t("archive.schedule.campaigns"), "items": sorted(campaigns, key=lambda c: c["when"]["start"])})
        sections.append({"key": "fortune", "label": t("archive.schedule.fortune_draws"), "items": [
            {"id": r["OmikujiId"], "title": t("archive.schedule.fortune_draw", n=r["OmikujiId"]), "when": when(r["StartDatetime"], r["EndDatetime"])}
            for r in sorted(self.m("m_omikuji"), key=lambda r: r["StartDatetime"])]})
        sections.append({"key": "comeback", "label": t("archive.schedule.welcome_back"), "items": [
            {"id": r["ComebackCampaignId"], "title": away(r["ComebackJudgeDayCount"], r["GrantCampaignTermDayCount"]),
             "when": when(r["ComebackJudgeStartDatetime"], r["ComebackJudgeEndDatetime"])}
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
                        entries.append((r["start"], BANNER_TARGETS[SUMMON], s["title"], r["label"], f"/schedule?tab=summons#summon-{s['id']}"))
        for k in self.events():
            for e in k["items"]:
                if e["when"]["limited"]:
                    entries.append((e["when"]["start"], e["kind"], e["title"], e["when"]["label"], f"/schedule?tab=events#event-{e['id']}"))
                for season in e["seasons"]:
                    if season["limited"]:
                        entries.append((season["start"], e["kind"], t("archive.schedule.event_season", title=e["title"], n=season["number"]), season["label"],
                                        f"/schedule?tab=events#event-{e['id']}"))
        for m in self.shops():
            for s in m["items"]:
                if s["when"]["limited"] and s["type"] != 4:  # an exchange runs with its summon
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
