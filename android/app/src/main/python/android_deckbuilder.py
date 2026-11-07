"""Pod Programs › Deck Builder: Arena decks picked the way experienced players
picked them, equipped from the game's data, with the game's exact Force, and
written to the deck slots the player chooses.

The engine is the deckbuilder package. Fully raised pieces are built by the
server's own upgrade actions on a staging save (the editing shim's
"deckbuilder_stage" target), rebuilt when the master data changes; a write is
the shim's "deck_write" (server/internal/lunarbase/bunker_deckwrite.go) after
one Save Data snapshot. Nothing but the chosen slots, the added pieces and the
ticked costumes changes.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from web import config
import android_runtime as runtime

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))
ARENA = 2
EFFECTS = ("compromise", "cleanse", "revive", "provoke", "dauntless", "indomitable", "from_start")
_lock = threading.Lock()
_sessions: dict = {}


class DeckBuilderError(Exception):
    """A refused write or edit: the shim's reason, for the player."""


def _shim(payload):
    from web.services import grant_service
    try:
        return grant_service._invoke_shim(payload)
    except grant_service.GrantError as exc:
        raise DeckBuilderError(str(exc)) from exc


def _backup():
    from web.services import backup_service
    backup_service.create_backup(reason="deck builder")


def result_key(result) -> str:
    return "-".join(str(c) for c in result.lineup)


def _stage_dir() -> Path:
    return Path(config.GAME_DB_PATH).parent / "deckbuilder"


# ---------------------------------------------------------------- the session

class Session:
    """One player's Deck Builder: master data, experts, their save, the stage
    and the generator; the last results by key."""

    def __init__(self, user_id: int):
        from deckbuilder import experts, generate, model, sim
        from deckbuilder.tables import Tables
        self.user_id = user_id
        self.tables = Tables(config.MASTERDATA_DIR, config.NAMES_DIR)
        sim.use(self.tables)
        self.experts = experts.Experts.load(self.tables)
        self.base = model.Save(model.connect_ro(config.GAME_DB_PATH), user_id)
        self.stage = model.Save(model.connect_ro(self.ensure_stage()), 1)
        self.gen = generate.Generator(self.tables, self.experts, self.base, self.stage)
        self.results = {}
        self._against = {}

    def ensure_stage(self) -> Path:
        """The staging save for this master data, built (by the server's own
        upgrades) when missing or made from other master data."""
        from deckbuilder import equip, stage
        folder = _stage_dir()
        path, marker = folder / "stage.db", folder / "stage.json"
        sig = runtime.fingerprint(config.find_master_data_bin())
        if path.exists() and runtime.read_json(marker) == {"master": sig}:
            return path
        from deckbuilder import generate
        pool = generate.default_pool(self.tables, self.experts)
        plan = equip.stage_plan([(c,) for c in pool] + [l.costumes for l in self.experts.lineups()], self.tables, self.experts)
        stage.Stager(lambda p: _shim(p), self.tables).build(**plan)
        folder.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"master": sig}))
        return path

    def against(self, opponent):
        """The deck to build against: an opponent from the matching list
        (their lineup, equipped as the data would), or None for General best."""
        if not opponent or opponent == "general":
            return None
        from deckbuilder import equip
        if opponent not in self._against:
            o = next((x for x in self.opponents() if str(x["id"]) == str(opponent)), None)
            if not o:
                return None
            lineup = tuple(c for c in o["costumes"] if c)
            self._against[opponent] = equip.equip(lineup, equip.Mode("best"), self.stage, self.stage, self.tables, self.experts,
                                                  deck_number=99).deck
        return self._against[opponent]

    def page(self, criteria, offset, limit):
        p = self.gen.page(criteria, offset, limit)
        for r in p.items:
            self.results[result_key(r)] = (r, criteria)
        return p

    def find(self, key):
        hit = self.results.get(key)
        return hit[0] if hit else None

    def tiles(self, r):
        new = {s.costume.uuid for s in r.equipped.specs if s and s.costume.source == "stage"}
        out = []
        for i, (c, e) in enumerate(zip(r.lineup, r.elements)):
            spec = r.equipped.specs[i]
            out.append({"name": self.tables.costume_name(c), "element": e, "slot": "LMR"[i], "new": bool(spec and spec.costume.uuid in new
                                                                                                          and self.base.pick("costume", costume_id=c) is None)})
        return out

    def detail(self, r):
        from deckbuilder import explain, model
        criteria = self.results[result_key(r)][1]
        e = explain.explain(r, criteria.against, self.tables, self.experts)
        from deckbuilder import power
        forces = [p.total for p in power.deck_power(r.deck, self.tables).characters]
        chars = []
        for i, c in enumerate(r.deck.characters()):
            if not c:
                continue
            spec = r.equipped.specs[i]
            pieces = [{"kind": "MAIN", "name": self.tables.name("weapons", c.main_weapon.id) if c.main_weapon else "—",
                       "new": bool(spec.main_weapon and spec.main_weapon.source == "stage"), "why": r.equipped.reasons.get((c.costume.id, "main_weapon"), "")}]
            pieces += [{"kind": "SUB", "name": self.tables.name("weapons", w.id), "new": s.source == "stage", "why": ""} for w, s in zip(c.subs, spec.subs)]
            if c.companion:
                pieces.append({"kind": "COMP", "name": self.tables.name("companions", c.companion.id), "new": spec.companion.source == "stage", "why": ""})
            if c.memoirs:
                pieces.append({"kind": "MEM", "name": f"{len(c.memoirs)} memoirs", "new": any(m.source == "stage" for m in spec.memoirs),
                               "why": r.equipped.reasons.get((c.costume.id, "memoirs"), "")})
            if c.debris:
                pieces.append({"kind": "DEB", "name": self.tables.name("thoughts", c.debris.id), "new": spec.debris.source == "stage", "why": ""})
            chars.append({"slot": ("Left", "Middle", "Right")[i], "name": self.tables.costume_name(c.costume.id), "line": e.per_character[i],
                          "element": r.elements[i], "force": forces[i], "pieces": pieces})
        inv = model.Inventory(self.base, self.tables)
        labels = {(s.deck_type, s.number): s.label for s in model.slots(self.base, self.tables)}
        raises = [{"costume_id": x.costume_id, "name": self.tables.costume_name(x.costume_id), "field": x.field, "current": x.current,
                   "target": x.target, "used_in": [labels.get(u, f"Deck {u[1]}") for u in x.used_in]}
                  for x in model.raises_needed(r.equipped.specs, self.base, self.stage, inv)]
        return {"title": e.title, "why_long": e.why_long, "characters": chars, "overrides": e.overrides, "raises": raises,
                "added": self.gen.added(r.equipped.to_add)}

    def rescore(self, r, raises):
        from deckbuilder import model, power
        criteria = self.results[result_key(r)][1]
        deck = model.compose(self.base, self.stage, r.equipped.specs, ARENA, 1, self.tables, raises=list(raises))
        return {"force": power.deck_power(deck, self.tables).total, "win_pct": round(100 * self.gen.rate(deck, criteria))}

    def opponents(self):
        try:
            data = _shim({"action": "arena_matching", "user_id": self.user_id}).get("data") or []
        except DeckBuilderError:
            return []
        return [dict(o, names=[self.tables.character_name(c) for c in o["costumes"] if c]) for o in data]

    def slots(self):
        from deckbuilder import model
        return [s._asdict() for s in model.slots(self.base, self.tables)]

    def players(self):
        try:
            from web.services import userdata_service
            return [(u.user_id, u.name or f"Player {u.user_id}") for u in userdata_service.list_users()]
        except Exception:
            return []


def session(user_id: int) -> Session:
    with _lock:
        s = _sessions.get(user_id)
        if s is None:
            s = _sessions[user_id] = Session(user_id)
        return s


def _user(user):
    if user:
        return int(user)
    import android_players
    return android_players.device_player() or 1


# ---------------------------------------------------------------- criteria

def _ints(text):
    return frozenset(int(x) for x in str(text or "").split(",") if x.strip().isdigit())


def criteria_from(s: Session | None, q: dict):
    from deckbuilder import equip, generate
    mode = equip.Mode("owned", int(q.get("allow") or 0)) if q.get("mode") == "owned" else equip.Mode("best")
    els = tuple((q.get(f"el_{k}") or None) for k in "lmr")
    must = frozenset(x for x in str(q.get("must") or "").split(",") if x in EFFECTS)
    mins = {k: int(q[f"min_{k}"]) for k in ("agi", "hp", "atk", "crit") if str(q.get(f"min_{k}") or "").isdigit() and int(q[f"min_{k}"]) > 0}
    against = s.against(q.get("against")) if s is not None and hasattr(s, "against") else None
    return generate.Criteria(deck_for=q.get("deck_for") or "attack", mode=mode, against=against, strategy=q.get("strategy") or "any",
                             elements=els, must_have=must, include=_ints(q.get("include")), exclude=_ints(q.get("exclude")),
                             exclude_elements=frozenset(x for x in str(q.get("exclude_el") or "").split(",") if x),
                             min_stats=mins, sort=q.get("sort") or "match")


def card(s, r) -> dict:
    return {"key": result_key(r), "rank": r.rank, "title": r.name, "win_pct": round(100 * r.win_rate), "tiles": s.tiles(r),
            "tags": r.tags[:3], "why": r.why, "force": r.force, "to_add": r.to_add, "variants": len(r.variants),
            "data_pick": {"beats": r.data_pick.beats, "by_pct": round(100 * r.data_pick.by)} if r.data_pick else None}


def _spec_json(spec):
    if spec is None:
        return None
    ref = lambda r: {"uuid": r.uuid, "source": r.source} if r else None
    return {"costume": ref(spec.costume), "main_weapon": ref(spec.main_weapon), "subs": [ref(x) for x in spec.subs],
            "companion": ref(spec.companion), "memoirs": [ref(x) for x in spec.memoirs], "debris": ref(spec.debris)}


# ---------------------------------------------------------------- routes

@router.get("/decks")
def page(request: Request, user: int = 0):
    user_id = _user(user)
    s = session(user_id)
    return templates.TemplateResponse(request, "deck_builder.html", {"active": "decks", "user": user_id, "players": s.players(),
                                                                     "slots": s.slots(), "opponents": s.opponents()})


@router.get("/decks/results")
def results(request: Request, user: int = 0, offset: int = 0, limit: int = 6):
    s = session(_user(user))
    c = criteria_from(s, dict(request.query_params))
    p = s.page(c, max(0, offset), max(1, min(limit, 24)))
    return {"total": p.total, "items": [card(s, r) for r in p.items], "exhausted": p.exhausted, "relax": p.relax}


@router.get("/decks/detail")
def detail(key: str, user: int = 0):
    s = session(_user(user))
    r = s.find(key)
    if r is None:
        return JSONResponse({"ok": False, "error": "That deck is no longer listed"}, status_code=404)
    return s.detail(r)


@router.get("/decks/rescore")
def rescore(request: Request, key: str, user: int = 0):
    """Force and win % with only the ticked costumes raised (?raise=id,id)."""
    s = session(_user(user))
    r = s.find(key)
    if r is None:
        return JSONResponse({"ok": False, "error": "That deck is no longer listed"}, status_code=404)
    return s.rescore(r, sorted(_ints(request.query_params.get("raise", ""))))


@router.get("/decks/opponents")
def opponents(user: int = 0):
    return session(_user(user)).opponents()


@router.post("/decks/write")
def write(payload: dict = Body(...)):
    user_id = _user(payload.get("user"))
    s = session(user_id)
    r = s.find(str(payload.get("key") or ""))
    if r is None:
        return JSONResponse({"ok": False, "error": "That deck is no longer listed"}, status_code=404)
    numbers = [int(n) for n in payload.get("slots") or [] if str(n).isdigit()]
    if not numbers:
        return JSONResponse({"ok": False, "error": "Choose a deck slot to write to"}, status_code=400)
    raises = sorted(_ints(",".join(str(x) for x in payload.get("raise") or [])))
    force = s.rescore(r, raises)["force"]
    deck = {"slots": [{"deck_type": ARENA, "number": n, "power": force} for n in numbers],
            "characters": [_spec_json(x) for x in r.equipped.specs], "raise": raises}
    try:
        _backup()
        _shim({"action": "deck_write", "user_id": user_id, "deck": deck})
    except (DeckBuilderError, ValueError, FileNotFoundError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    with _lock:
        _sessions.pop(user_id, None)        # the save changed: read it again
    return {"ok": True, "added": s.gen.added(r.equipped.to_add), "raised": raises, "slots": numbers}
