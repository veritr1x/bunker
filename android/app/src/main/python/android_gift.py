"""Pod Programs › Gift: send yourself anything the game can hold.

It arrives in the game's own Gift Box as "From Bunker, with love." (m_gift_text
GIFT_TEXT_ID, patches/bunker-gift-text.patch), never expires, and is claimed
there under the game's own rules. The gift is written by the editing shim's
"send_gift" action (server/internal/lunarbase/bunker_gift.go), which also says
how much of a thing can still be claimed ("gift_room").
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from web import config
import android_runtime as runtime

GIFT_TEXT_ID = 90000

# model.PossessionType
COSTUME, WEAPON, COMPANION, PARTS, MATERIAL, CONSUMABLE, PAID_GEM, FREE_GEM, THOUGHT = 1, 2, 3, 4, 5, 6, 11, 12, 14
# m_weapon AttributeType (masterdata/bunker_elements.go)
ELEMENTS = {1: "Dark", 2: "Fire", 3: "Light", 5: "Water", 6: "Wind"}
NEVER = 4_000_000_000_000


@dataclass
class Entry:
    name: str
    stars: int
    possession_type: int
    possession_id: int
    one_per_gift: bool = False


@dataclass
class Group:
    name: str
    entries: list[Entry] = field(default_factory=list)


@dataclass
class Card:
    name: str
    groups: list[Group]


def _names(kind):
    data = runtime.read_json(config.NAMES_DIR / f"{kind}.json", {}) or {}
    return [r for r in data.get("records", []) if isinstance(r, dict) and r.get("name_found") and r.get("name")]


def _table(name):
    return [r for r in runtime.read_json(config.MASTERDATA_DIR / f"EntityM{name}Table.json", []) or [] if isinstance(r, dict)]


def _stars(r):
    return int(r.get("RarityType") or 0) // 10


def _once(entries):
    """One entry per name, the first kept."""
    seen, out = set(), []
    for e in entries:
        if e.name not in seen:
            seen.add(e.name)
            out.append(e)
    return out


def _consumables(now_ms):
    """Consumable items by name: of copies sharing a name (event-bound items,
    each tied to one event's dates), the one usable at now_ms, else one without
    dates, else the one ending last."""
    terms = {t.get("ConsumableItemTermId"): (t.get("StartDatetime", 0), t.get("EndDatetime", NEVER)) for t in _table("ConsumableItemTerm")}
    by_name = {}
    for r in _names("consumables"):
        by_name.setdefault(r["name"], []).append(r)

    def rank(r):
        start, end = terms.get(r.get("ConsumableItemTermId"), (0, NEVER))
        if not r.get("ConsumableItemTermId"):
            return (1, NEVER, -r["id"])
        return (2 if start <= now_ms <= end else 0, end, -r["id"])
    return [max(copies, key=rank) for copies in by_name.values()]


def catalog(now_ms: int) -> list[Card]:
    """The six cards of the Gift page, by what a thing is for (the design's
    category table)."""
    cons = sorted(_consumables(now_ms), key=lambda r: r["id"])
    mats = _names("materials")

    def items(*types):
        return _once(Entry(r["name"], 0, CONSUMABLE, r["id"]) for r in cons if r.get("ConsumableItemType") in types)

    def materials(kind):
        return _once(Entry(r["name"], _stars(r), MATERIAL, r["id"]) for r in mats if r.get("MaterialType") == kind)

    gold = [Entry(r["name"], 0, CONSUMABLE, r["id"]) for r in cons if r.get("ConsumableItemType") == 100]
    currency = [Entry("Gems", 0, FREE_GEM, 0), Entry("Paid Gems", 0, PAID_GEM, 0)] + gold

    weapon_ids = {r.get("WeaponId") for r in _table("CatalogWeapon")}
    weapons = [r for r in _names("weapons") if r["id"] in weapon_ids]
    shared = {n for n, k in Counter(r["name"] for r in weapons).items() if k > 1}
    weapons = _once(Entry(r["name"] + (f" ({ELEMENTS.get(r.get('AttributeType'), '?')})" if r["name"] in shared else ""),
                          _stars(r), WEAPON, r["id"]) for r in weapons)

    groups = {r.get("PartsGroupId") for r in _table("CatalogPartsGroup")}
    seen, memoirs = set(), []
    for r in _names("parts"):
        if r.get("PartsGroupId") in groups and (r["name"], r.get("RarityType")) not in seen:
            seen.add((r["name"], r.get("RarityType")))
            memoirs.append(Entry(r["name"], _stars(r), PARTS, r["id"]))

    thought_ids = {r.get("ThoughtId") for r in _table("CatalogThought")}
    thoughts = [r for r in _names("thoughts") if r["id"] in thought_ids]
    count, number, debris = Counter(r["name"] for r in thoughts), Counter(), []
    for r in thoughts:
        name = r["name"]
        if count[name] > 1:
            number[name] += 1
            name = f"{name} · {number[name]}"
        debris.append(Entry(name, _stars(r), THOUGHT, r["id"], True))

    companion_ids = {r.get("CompanionId") for r in _table("CatalogCompanion")}
    companions = _once(Entry(r["name"], 0, COMPANION, r["id"], True) for r in _names("companions") if r["id"] in companion_ids)
    characters = _once(Entry(f"{r['character_name']} ({r['name']})" if r.get("character_name") else r["name"], _stars(r), COSTUME, r["id"], True)
                       for r in _names("playable_costumes"))

    return [
        Card("Currency", [Group("Gems & gold", currency), Group("Medals & coins", items(110, 130))]),
        Card("Summoning", [Group("Summon tickets", items(200)), Group("Summon shards", items(120))]),
        Card("Character growth", [Group("Enhancement", materials(20)), Group("Handbooks", materials(90)),
                                  Group("Wish fragments", materials(40)), Group("Insignias & agents", materials(50)),
                                  Group("Awakening stones", materials(110)), Group("Karma stones", materials(140)),
                                  Group("Verses", materials(120))]),
        Card("Weapon growth", [Group("Enhancement", materials(10)), Group("Slabs & antler bits", materials(100)),
                               Group("Adamant", materials(130)), Group("Gemstones", materials(70)),
                               Group("Minerals", materials(60)), Group("Pearls & crystals", materials(80))]),
        Card("Collection", [Group("Characters", characters), Group("Weapons", weapons), Group("Companions", companions),
                            Group("Memoirs", memoirs), Group("Debris", debris)]),
        Card("Everyday", [Group("Stamina", items(300)), Group("Skip & explorer tickets", items(201, 202)),
                          Group("Fish", materials(30))]),
    ]


def game_now() -> int:
    """The game's clock: the Original calendar's when it is on, else real time."""
    import android_calendar as calendar
    state = calendar.read_state()
    return calendar.game_now(state) if state else calendar.now_ms()
