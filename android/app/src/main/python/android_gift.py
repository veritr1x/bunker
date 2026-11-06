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


# --- Sending ------------------------------------------------------------------

import contextlib
import sqlite3

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

router = APIRouter()
# What a kind's name lives under in config.NAMES_DIR, by possession type.
NAME_FILES = {COSTUME: "playable_costumes", WEAPON: "weapons", COMPANION: "companions", PARTS: "parts",
              MATERIAL: "materials", CONSUMABLE: "consumables", THOUGHT: "thoughts"}


class GiftError(Exception):
    """A gift refused: the shim's or the page's reason, for the player."""


def _shim(payload):
    """The editing shim (android_runtime.adapt_services routes it to the native
    bridge and returns its result)."""
    from web.services import grant_service
    try:
        return grant_service._invoke_shim(payload)
    except grant_service.GrantError as exc:
        raise GiftError(str(exc)) from exc


def _backup():
    from web.services import backup_service
    backup_service.create_backup(reason="gift")


def _master():
    return str(config.find_master_data_bin())


def has_gift_text() -> bool:
    """Whether the game data the game launches with has "From Bunker, with love."."""
    return any(r.get("GiftTextId") == GIFT_TEXT_ID for r in _table("GiftText"))


def add_gift_text(source, output) -> bool:
    """Writes source's game data to output with the gift text added (the
    patcher's m_gift_text rows) and nothing else changed. False when source
    has it already (output is not written)."""
    import android_calendar as calendar
    from patcher import patch_masterdata as pm
    toc, blob = calendar.read_master(source)
    changed = {}
    if not pm.apply_to_table(toc, blob, changed, "m_gift_text", lambda b: pm.add_table_rows(b, pm.TABLE_ROW_ADDITIONS["m_gift_text"])):
        return False
    calendar.write_master(toc, blob, changed, output)
    return True


def _add_gift_text_to_game():
    """Gives the game data in use the gift text: game data made before this
    build, imported or restored has none. The old data is kept as a snapshot
    (Content › Previous versions), and a preset stays a preset."""
    import android_patcher as patcher
    candidate = patcher.folder() / "candidate.bin.e"
    try:
        import android_challenges as challenges
        if not add_gift_text(challenges.unchallenged_master(), candidate):
            return
        active = runtime.read_json(patcher.folder() / "active.json")
        label = active.get("label") if isinstance(active, dict) and active.get("sha256") == runtime.fingerprint(config.find_master_data_bin()) else None
        patcher.activate(candidate, label or "Imported master data")
    finally:
        candidate.unlink(missing_ok=True)


def _request(action, user_id, possession_type, possession_id, **extra):
    return dict({"action": action, "db_path": str(config.GAME_DB_PATH), "master_data_path": _master(), "user_id": int(user_id),
                 "possession_type": int(possession_type), "possession_id": int(possession_id)}, **extra)


def room(user_id: int, possession_type: int, possession_id: int) -> int:
    """How many more of a thing can be sent now and still be claimed."""
    result = _shim(_request("gift_room", user_id, possession_type, possession_id)) or {}
    return int(result.get("applied", 0))


def send(user_id: int, possession_type: int, possession_id: int, count: int) -> bool:
    """Puts a gift in the game's Gift Box (one backup first). Game data without
    the gift text gets it first; True then: the game must load its data again."""
    added = not has_gift_text()
    if added:
        _add_gift_text_to_game()
    _backup()
    _shim(_request("send_gift", user_id, possession_type, possession_id, count=int(count)))
    return added


def _gift_rows(user_id, where, *args):
    if not config.GAME_DB_PATH.is_file():
        return []
    with contextlib.closing(sqlite3.connect(f"file:{config.GAME_DB_PATH}?mode=ro", uri=True)) as db:
        return db.execute("SELECT possession_type, possession_id, count, grant_datetime, description_gift_text_id, expiration_datetime"
                          " FROM user_gifts WHERE user_id = ? AND is_received = 0 AND " + where, (user_id, *args)).fetchall()


def _name(possession_type, possession_id):
    if possession_type == FREE_GEM:
        return "Gems"
    if possession_type == PAID_GEM:
        return "Paid Gems"
    kind = NAME_FILES.get(possession_type)
    for r in _names(kind) if kind else ():
        if r["id"] == possession_id:
            return f"{r['character_name']} ({r['name']})" if possession_type == COSTUME and r.get("character_name") else r["name"]
    return f"#{possession_id}"


def waiting(user_id: int) -> list[dict]:
    """The Bunker gifts not claimed yet (they never expire), newest first."""
    rows = _gift_rows(user_id, "description_gift_text_id = ?", GIFT_TEXT_ID)
    out = [{"possession_type": t, "possession_id": i, "count": n, "sent": at, "name": _name(t, i)} for t, i, n, at, _, _ in rows]
    return sorted(out, key=lambda g: -g["sent"])


def waiting_count(user_id: int, now_ms: int | None = None) -> int:
    """Every unclaimed gift in the Gift Box that has not expired."""
    now_ms = game_now() if now_ms is None else now_ms
    return len(_gift_rows(user_id, "(expiration_datetime IS NULL OR expiration_datetime = 0 OR expiration_datetime >= ?)", now_ms))


def _user(user):
    if user:
        return int(user)
    import android_players
    return android_players.device_player() or 1


@router.get("/gift/room")
def room_route(type: int, id: int, user: int = 0):
    try:
        return {"room": room(_user(user), type, id)}
    except GiftError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@router.get("/gift/waiting-count")
def waiting_count_route(user: int = 0):
    return {"count": waiting_count(_user(user))}


@router.post("/gift/send")
def send_route(payload: dict = Body(...)):
    try:
        values = [payload[k] for k in ("user", "possession_type", "possession_id", "count")]
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            raise ValueError("whole numbers only")
        user, kind, ident, count = values
    except (KeyError, TypeError, ValueError):
        return JSONResponse({"ok": False, "error": "user, possession_type, possession_id and count are required"}, status_code=400)
    try:
        added = send(_user(user), kind, ident, count)
    except GiftError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    if added:  # the game data changed too: the game goes back to its title screen to load it
        return JSONResponse({"ok": True})
    # The save changed, but the game reads gifts from the server on its next
    # call: Lunar Tear restarts around the change and the game plays on.
    return JSONResponse({"ok": True}, headers={"X-Bunker-Keep-Playing": "1"})


# --- The page -----------------------------------------------------------------

from dataclasses import asdict

from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))


def _owned_debris(user_id):
    try:
        from web.services import userdata_service
        return userdata_service.get_owned_thought_ids(user_id)
    except Exception:  # no save yet
        return set()


def _players():
    try:
        from web.services import userdata_service
        return [(u.user_id, u.name or f"Player {u.user_id}") for u in userdata_service.list_users()]
    except Exception:
        return []


def page_cards(user_id: int) -> list[dict]:
    """The catalog for the page; debris that can't be sent say why ("blocked"):
    owned (the game gives nothing for a second one) or already in the Gift Box."""
    owned = _owned_debris(user_id)
    waiting_debris = {g["possession_id"] for g in waiting(user_id) if g["possession_type"] == THOUGHT}

    def blocked(e):
        if e.possession_type != THOUGHT:
            return ""
        return "Owned" if e.possession_id in owned else "In Gift Box" if e.possession_id in waiting_debris else ""
    return [{"name": c.name, "groups": [{"name": g.name, "entries": [dict(asdict(e), blocked=blocked(e)) for e in g.entries]}
                                        for g in c.groups]} for c in catalog(game_now())]


@router.get("/gift")
def page(request: Request, user: int = 0, message: str = "", error: str = ""):
    user_id = _user(user)
    cards = page_cards(user_id)
    return templates.TemplateResponse(request, "gift.html", {"active": "gift", "cards": cards, "user": user_id, "players": _players(),
                                                             "ready": has_gift_text(), "waiting": waiting(user_id),
                                                             "message": message, "error": error})
