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
import bunker_text  # noqa: E402
bunker_text.install(templates)  # Bunker's own text, in the chosen language
ARENA = 2
ARENA_TABLE_SIZE = 300     # decks in the Arena deck table
EFFECTS = ("compromise", "cleanse", "revive", "provoke", "dauntless", "indomitable", "from_start")
_lock = threading.Lock()
_sessions: dict = {}


class DeckBuilderError(Exception):
    """A refused write or edit: the shim's reason, for the player."""


class StageNotReady(Exception):
    """The staging save is missing, made from other data, or lacks these
    costumes: POST /decks/prepare builds it (the game guard pauses the
    server for it, as building loads master data the server reads)."""

    def __init__(self, extra=()):
        super().__init__("The Deck Builder stage is not ready")
        self.extra = tuple(extra)


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
        self.lock = threading.RLock()
        self.tables = _tables_for(runtime.fingerprint(config.find_master_data_bin()))
        sim.use(self.tables)
        self.experts = experts.Experts.load(self.tables)
        self.base = model.Save(model.snapshot(config.GAME_DB_PATH), user_id)    # read again after a write (drop_session)
        path = stage_ready(self.tables, self.experts)
        if path is None:
            raise StageNotReady()
        self._open_stage(path)

    def _open_stage(self, path):
        from deckbuilder import generate, model
        self.stage = model.Save(model.snapshot(path), 1)
        self.gen = generate.Generator(self.tables, self.experts, self.base, self.stage, best_pool=_stage_pool(),
                                      baked=_baked() if _stage_baked_ok() else None)
        self.results = {}
        self._against = {}
        self.loadouts = {}          # Subjugation loadouts by key
        self._subjugation = {}

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
            lineup = tuple(c for c in o["costumes"] if c and c in self.tables.idx("Costume", "CostumeId"))
            staged = {r["costume_id"] for r in self.stage.q("select costume_id from user_costumes where user_id=?")}
            if not set(lineup) <= staged:     # an opponent outside the stage: prepare stages their costumes
                raise StageNotReady(extra=lineup)
            self._against[opponent] = equip.equip(lineup, equip.Mode("best"), self.stage, self.stage, self.tables, self.experts,
                                                  deck_number=99).deck
        return self._against[opponent]

    def page(self, criteria, offset, limit):
        self._staged(criteria)
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
            out.append({"id": c, "name": self.tables.costume_name(c), "element": e, "slot": "LMR"[i], "new": bool(spec and spec.costume.uuid in new
                                                                                                          and self.base.pick("costume", costume_id=c) is None)})
        return out

    def detail(self, r):
        from deckbuilder import explain, model
        criteria = self.results[result_key(r)][1]
        e = explain.explain(r, criteria.against, self.tables, self.experts)
        chars = self.characters(r.deck, r.equipped, r.elements, e.per_character)
        return {"title": e.title, "why_long": e.why_long, "characters": chars, "overrides": e.overrides,
                "raises": self.raises(r.equipped.specs), "added": self.gen.added(r.equipped.to_add)}

    def raises(self, specs):
        from deckbuilder import model
        inv = model.Inventory(self.base, self.tables)
        labels = {(s.deck_type, s.number): s.label for s in model.slots(self.base, self.tables)}
        return [{"costume_id": x.costume_id, "name": self.tables.costume_name(x.costume_id), "field": x.field, "current": x.current,
                 "target": x.target, "used_in": [labels.get(u, f"Deck {u[1]}") for u in x.used_in]}
                for x in model.raises_needed(specs, self.base, self.stage, inv)]

    def characters(self, deck, equipped, elements, lines):
        """Each character of a deck with its pieces, as the deck view lists them."""
        from deckbuilder import power
        forces = [p.total for p in power.deck_power(deck, self.tables).characters]
        chars = []
        for i, c in enumerate(deck.characters()):
            if not c:
                continue
            spec = equipped.specs[i]
            reasons = equipped.reasons
            icon = lambda kind, pid: f"/decks/icon/{kind}/{pid}.png"
            # Each piece as the game's notices show it: its icon and name; why it is there, behind an ⓘ.
            pieces = [{"kind": "MAIN", "label": "Main weapon", "name": self.tables.name("weapons", c.main_weapon.id) if c.main_weapon else "—",
                       "icon": icon("weapon", c.main_weapon.id) if c.main_weapon else None,
                       "new": bool(spec.main_weapon and spec.main_weapon.source == "stage"), "why": reasons.get((c.costume.id, "main_weapon"), "")}]
            pieces += [{"kind": "SUB", "label": "Sub weapon", "name": self.tables.name("weapons", w.id), "icon": icon("weapon", w.id),
                        "new": s.source == "stage", "why": ""} for w, s in zip(c.subs, spec.subs)]
            if c.companion:
                pieces.append({"kind": "COMP", "label": "Companion", "name": self.tables.name("companions", c.companion.id),
                               "icon": icon("companion", c.companion.id), "new": spec.companion.source == "stage", "why": ""})
            if c.memoirs:
                pieces.append({"kind": "MEM", "label": f"Memoirs ×{len(c.memoirs)}", "name": self.tables.memoir_set_name(c.memoirs[0].id) or "Memoirs",
                               "icon": icon("memoir", c.memoirs[0].id), "new": any(m.source == "stage" for m in spec.memoirs),
                               "why": reasons.get((c.costume.id, "memoirs"), "")})
            if c.debris:
                pieces.append({"kind": "DEB", "label": "Debris", "name": self.tables.name("thoughts", c.debris.id).removeprefix("Debris: "),
                               "icon": icon("debris", c.debris.id),
                               "new": spec.debris.source == "stage" and self.base.pick("debris", thought_id=c.debris.id) is None, "why": ""})
            chars.append({"slot": ("Left", "Middle", "Right")[i], "costume_id": c.costume.id,
                          "name": self.tables.costume_name(c.costume.id), "line": lines[i] if lines else "",
                          "element": elements[i], "force": forces[i], "pieces": pieces})
        return chars

    def costumes(self, mode):
        """Every costume the filters' character picker offers, in one list by character then costume: in What I own
        the player's, else every playable one."""
        known = self.tables.idx("Costume", "CostumeId")
        if mode == "owned":
            every = {r["costume_id"] for r in self.base.q("select costume_id from user_costumes where user_id=?")}
        else:
            every = set(known)
        every = sorted((c for c in every if c in known and self.tables.is_fieldable(c)),
                       key=lambda c: (self.tables.character_name(c), self.tables.costume_name(c), c))
        return [{"id": c, "name": self.tables.costume_name(c), "character": self.tables.character_name(c),
                 "element": self.tables.costume_element(c) or "dark"} for c in every]

    def _staged(self, criteria):
        """All maxed: required costumes the stage lacks must be staged first (prepare)."""
        if criteria.mode.kind != "best" or not criteria.include:
            return
        staged = {r["costume_id"] for r in self.stage.q("select costume_id from user_costumes where user_id=?")}
        missing = tuple(sorted(set(criteria.include) - staged))
        if missing:
            raise StageNotReady(extra=missing)

    # ---------------------------------------------------------------- Subjugation
    def bosses(self):
        from deckbuilder import bighunt
        return [{"id": b.id, "name": b.name, "element": b.element} for b in bighunt.bosses(self.tables) if b.fights]

    def subjugation(self, boss_id, difficulty, criteria):
        """The best loadouts (three decks, nine characters) against a boss; run once per boss, difficulty and criteria."""
        from deckbuilder import bighunt, subjugation
        b = bighunt.boss(self.tables, boss_id)
        if b is None or not b.fights:
            return []
        difficulty = difficulty if difficulty in b.fights else max(b.fights)
        self._staged(criteria)
        c = criteria       # the filters that change the lineups (no dict in a key: minimum stats as sorted pairs)
        key = (boss_id, difficulty, c.mode, c.strategy, c.elements, c.must_have, c.include, c.exclude, c.exclude_elements,
               tuple(sorted((c.min_stats or {}).items())))
        if key not in self._subjugation:
            self._subjugation[key] = subjugation.rank(self.gen, b, difficulty, criteria.mode, criteria=criteria)
            for lo in self._subjugation[key]:
                self.loadouts[lo.key] = lo
        return self._subjugation[key]

    def find_loadout(self, key):
        return self.loadouts.get(key)

    def loadout_detail(self, lo):
        from deckbuilder import bighunt
        b = bighunt.boss(self.tables, lo.boss_id)
        decks = [{"phase": d.phase, "number": 100 + d.phase, "title": d.name, "strategy": d.strategy, "damage": d.damage,
                  "knockdowns": d.knockdowns, "standing": d.standing, "force": d.force,
                  "characters": self.characters(d.deck, d.equipped, d.elements, None)} for d in lo.decks]
        specs = [s for d in lo.decks for s in d.equipped.specs]
        return {"kind": "subjugation", "title": b.name if b else "Subjugation", "difficulty": lo.difficulty, "decks": decks,
                "raises": self.raises(specs), "added": sum(self.gen.added(d.equipped.to_add) for d in lo.decks)}

    def loadout_force(self, lo, raises):
        """Each deck's exact Force as written (101, 102, 103), with the ticked costumes raised."""
        from deckbuilder import model, power
        out = []
        for d in lo.decks:
            mine = [c for c in raises if c in d.lineup]
            deck = model.compose(self.base, self.stage, d.equipped.specs, 5, 100 + d.phase, self.tables, raises=mine)
            out.append(power.deck_power(deck, self.tables).total)
        return out

    def loadout_raisable(self, lo):
        from deckbuilder import model
        inv = model.Inventory(self.base, self.tables)
        return {x.costume_id for d in lo.decks for x in model.raises_needed(d.equipped.specs, self.base, self.stage, inv)}

    def force(self, r, raises):
        """The written deck's exact Force (no fights simulated)."""
        from deckbuilder import model, power
        deck = model.compose(self.base, self.stage, r.equipped.specs, ARENA, 1, self.tables, raises=list(raises))
        return power.deck_power(deck, self.tables).total

    def raisable(self, r):
        """Owned costumes of this deck the stage holds higher: the ones a write may raise."""
        from deckbuilder import model
        inv = model.Inventory(self.base, self.tables)
        return {x.costume_id for x in model.raises_needed(r.equipped.specs, self.base, self.stage, inv)}

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


def _locked(fn):
    """A Session is used by one thread at a time (requests and the Arena refresh)."""
    import functools

    @functools.wraps(fn)
    def run(self, *a, **kw):
        with self.lock:
            return fn(self, *a, **kw)
    return run


for _name in ("page", "find", "tiles", "detail", "force", "raisable", "rescore", "against", "opponents", "slots"):
    setattr(Session, _name, _locked(getattr(Session, _name)))


def _stage_files():
    folder = _stage_dir()
    return folder / "stage.db", folder / "stage.json"


SCREEN = 1      # All maxed's pool chosen by strength (screen.py); a stage made before it is made again


_BAKED = []


def _baked():
    """The baked All maxed results shipped with this build (deckbuilder/data/baked), or None."""
    if not _BAKED:
        from deckbuilder import baked
        _BAKED.append(baked.Baked.load())
    return _BAKED[0]


def _baked_plan(b, tables) -> dict:
    """What the stage must hold to write any baked deck: every baked costume and piece, both roles' memoirs of each
    baked memoir set, each costume's baked karma."""
    from deckbuilder import equip
    los = list(b.loadouts.values()) + list(b.force_loadouts.values()) + \
        [lo for d in b.meta_decks for lo in d["loadouts"]]                 # the fights', the Force list's, the opponents'

    sets = sorted({lo["memoir_set"] for lo in los if lo.get("memoir_set")})
    return dict(costume_ids=sorted(set(b.loadouts) | set(b.force_loadouts) | {lo["costume_id"] for lo in los}),
                weapon_ids=sorted({w for lo in los for w in [lo["main_weapon"], *lo["subs"]] if w}),
                companion_ids=sorted({lo["companion"] for lo in los if lo.get("companion")}),
                thought_ids=sorted({lo["debris"] for lo in los if lo.get("debris")}),
                memoirs=[m for s in sets for _, mains, subs in equip.ROLE_MEMOIRS.values() for m in equip.memoir_specs(s, mains, subs, tables)],
                costume_karma={c: lo["karma"] for c, lo in b.loadouts.items() if lo.get("karma")})     # the bake's best karma


def _merge_plans(a: dict, b: dict) -> dict:
    out = {}
    for k in ("costume_ids", "weapon_ids", "companion_ids", "thought_ids"):
        out[k] = sorted(set(a.get(k) or []) | set(b.get(k) or []))
    memoirs = []
    for m in (a.get("memoirs") or []) + (b.get("memoirs") or []):
        if m not in memoirs:
            memoirs.append(m)
    out["memoirs"] = memoirs
    out["costume_karma"] = {**(a.get("costume_karma") or {}), **(b.get("costume_karma") or {})}
    for k in a:
        out.setdefault(k, a[k])
    return out


def _baked_check(tables, experts, path, b):
    """(whether this stage's fighters are the ones the bake simulated, the fingerprint here): every baked costume's
    fighter in its baked loadout and the meta decks' fighters (baked.fingerprint). Built once, after staging."""
    from deckbuilder import baked, fighters, generate, model, sim
    try:
        sim.use(tables)
        from deckbuilder.sim import battle
        st = model.Save(model.snapshot(path), 1)
        cache, keys = fighters.FighterCache(tables, st), {}
        for label, los in (("fight", b.loadouts), ("force", b.force_loadouts)):
            for c, lo in los.items():
                keys[(label, c)] = (label, c, lo["debris"])
                cache.add(keys[(label, c)], baked.loadout_spec(lo, st, tables))
        # the experts' meta decks the bake was scored against, in its loadouts (its own top decks are its fighters, above)
        decks = [baked.meta_deck(d, i, st, tables) for i, d in enumerate(b.meta_decks)] if b.meta_decks else \
            [d for d, _, _ in generate.Generator(tables, experts, st, st).meta()]
        sides = [battle._side(d, tables) for d in decks]
        fp = baked.fingerprint(cache, keys, sides)
        return fp == b.fingerprint, fp
    except Exception as exc:  # noqa: BLE001 (a piece missing from the stage: the live search, as before)
        return False, f"error: {exc}"


def _stage_baked_ok() -> bool:
    return bool((runtime.read_json(_stage_files()[1]) or {}).get("baked_ok"))


def _stage_want(extra=()):
    """(what the stage was made from, what it should be made from); what it chose (the pool, the baked check) is kept
    beside, not compared."""
    old = runtime.read_json(_stage_files()[1]) or {}
    extras = sorted(set(old.get("extra") or []) | set(extra))
    old = {k: v for k, v in old.items() if k not in ("pool", "baked_ok", "baked_here")}
    b = _baked()
    return old, {"master": runtime.fingerprint(config.find_master_data_bin()), "data": _data_signature(), "extra": extras,
                 "screen": SCREEN, "baked": b.fingerprint if b else None}


def _stage_pool():
    """The pool prepare chose by strength for the current stage, or None."""
    return (runtime.read_json(_stage_files()[1]) or {}).get("pool")


def stage_ready(tables, experts, extra=()):
    """The staging save's path when it was made from this master data, this
    build's expert and ranking data and holds these costumes; else None."""
    path, _ = _stage_files()
    old, want = _stage_want(extra)
    return path if path.exists() and old == want else None


def prepare(user_id: int, against=None, costumes=()) -> None:
    """Build the staging save (by the server's own upgrades): this build's pool
    and expert lineups, plus an opponent's costumes when one is named."""
    from deckbuilder import equip, experts as experts_mod, generate, stage
    tables = _tables_for(runtime.fingerprint(config.find_master_data_bin()))
    experts = experts_mod.Experts.load(tables)
    extra = ()
    if against and against != "general":
        try:
            data = _shim({"action": "arena_matching", "user_id": user_id}).get("data") or []
        except DeckBuilderError:
            data = []
        known = tables.idx("Costume", "CostumeId")
        extra = tuple(c for o in data if str(o["id"]) == str(against) for c in o["costumes"] if c in known)
    known = tables.idx("Costume", "CostumeId")
    extra = tuple(dict.fromkeys(list(extra) + [int(c) for c in costumes if str(c).isdigit() and int(c) in known]))
    with _lock:
        if stage_ready(tables, experts, extra) is None:
            _, want = _stage_want(extra)
            from deckbuilder import model, screen
            ranked = screen.strength(tables, experts, model.Save(model.snapshot(config.GAME_DB_PATH), user_id))
            pool = screen.pool_by_strength(ranked, tables) or generate.default_pool(tables, experts)
            lineups = [(c,) for c in pool + list(want["extra"])] + [l.costumes for l in experts.lineups()]
            plan = equip.stage_plan(lineups, tables, experts)
            b = _baked()
            if b is not None:
                plan = _merge_plans(plan, _baked_plan(b, tables))     # every baked deck can be written from it
            stage.Stager(lambda p: _shim(p), tables).build(**plan)
            ok, here = _baked_check(tables, experts, _stage_files()[0], b) if b is not None else (False, None)
            _stage_dir().mkdir(parents=True, exist_ok=True)
            _stage_files()[1].write_text(json.dumps(dict(want, pool=pool, baked_ok=ok, baked_here=here)))
        _sessions.clear()


_tables_cache: dict = {}
_tables_lock = threading.Lock()


def _tables_for(signature):
    """One Tables per master data: the simulator reloads its modules when
    the Tables object changes, so sessions share it."""
    from deckbuilder.tables import Tables
    with _tables_lock:      # not _lock: session() holds that while a Session is made
        if signature not in _tables_cache:
            _tables_cache.clear()
            _tables_cache[signature] = Tables(config.MASTERDATA_DIR, config.NAMES_DIR)
        return _tables_cache[signature]


def _data_signature():
    """The shipped expert and ranking data the stage was planned from."""
    import hashlib
    h = hashlib.sha256()
    for name in ("experts.json", "rankings.json"):
        h.update((Path(__file__).resolve().parent / "deckbuilder" / "data" / name).read_bytes())
    return h.hexdigest()


def drop_session(user_id: int) -> None:
    with _lock:
        _sessions.pop(user_id, None)


def _retrying(user_id, run):
    """run(session); after a database error, once more on a session read afresh."""
    import sqlite3
    try:
        return run(session(user_id))
    except sqlite3.DatabaseError:
        drop_session(user_id)
        return run(session(user_id))


def session(user_id: int) -> Session:
    with _lock:
        s = _sessions.get(user_id)
        if s is None:
            s = _sessions[user_id] = Session(user_id)
        return s


def _arena_files():
    folder = Path(config.GAME_DB_PATH).parent
    from deckbuilder import ladder
    return folder / ladder.DECK_FILE, folder / ladder.PLAYER_FILE


def _refresh_arena_now(user_id: int) -> None:
    """The Arena ladder's data (server/internal/pvp/decktable.go): the deck
    table when the master data changed, and this player's score."""
    from deckbuilder import ladder
    try:
        s = session(user_id)
    except StageNotReady:
        return              # the page prepares it; the ladder keeps its last data until then
    decks, players = _arena_files()
    sig = runtime.fingerprint(config.find_master_data_bin())
    with s.lock:
        if ladder.needs_export(decks, sig):
            from deckbuilder import equip
            ladder.export_table(s.tables, s.experts, s.stage, decks, size=ARENA_TABLE_SIZE,
                                pool=s.gen.pool(equip.Mode("best")), master_sha=sig)     # the pool the stage holds
        ladder.write_player_score(players, user_id, ladder.score_player(s.base, s.tables, s.experts, s.stage))


def refresh_arena(user_id: int) -> None:
    """In the background: the page never waits for it."""
    def run():
        try:
            with _refresh_lock:
                _refresh_arena_now(user_id)
        except Exception as exc:   # the ladder keeps its last data
            import logging
            logging.getLogger("deckbuilder").warning("Arena data not refreshed: %s", exc)
    threading.Thread(target=run, daemon=True).start()


_refresh_lock = threading.Lock()


def _user(user):
    if user:
        return int(user)
    import android_players
    return android_players.device_player() or 1


# ---------------------------------------------------------------- criteria

def _ints(text):
    return frozenset(int(x) for x in str(text or "").split(",") if x.strip().isdigit())


ALLOW_ALL = 999      # "All": What I own with no limit on the pieces added (a deck holds far fewer)


def criteria_from(s: Session | None, q: dict):
    from deckbuilder import equip, generate
    allow = str(q.get("allow") or "0")
    allow = ALLOW_ALL if allow == "all" else int(allow) if allow.isdigit() else 0
    mode = equip.Mode("owned", allow) if q.get("mode") == "owned" else equip.Mode("best")
    els = tuple((q.get(f"el_{k}") or None) for k in "lmr")
    must = frozenset(x for x in str(q.get("must") or "").split(",") if x in EFFECTS)
    mins = {k: int(q[f"min_{k}"]) for k in ("agi", "hp", "atk", "crit") if str(q.get(f"min_{k}") or "").isdigit() and int(q[f"min_{k}"]) > 0}
    against = s.against(q.get("against")) if s is not None and hasattr(s, "against") else None
    return generate.Criteria(deck_for=q.get("deck_for") or "attack", mode=mode, against=against, strategy=q.get("strategy") or "any",
                             elements=els, must_have=must, include=_ints(q.get("include")), exclude=_ints(q.get("exclude")),
                             exclude_elements=frozenset(x for x in str(q.get("exclude_el") or "").split(",") if x),
                             min_stats=mins, sort=q.get("sort") or "match")


def card(s, r) -> dict:
    from deckbuilder import generate
    return {"key": result_key(r), "rank": r.rank, "title": r.name, "win_pct": round(100 * r.win_rate), "tiles": s.tiles(r),
            "strategy": generate.STRATEGY_NAME.get(r.strategy, ""), "expert": bool(r.expert),
            "tags": r.tags[:3], "why": r.why, "force": r.force, "to_add": r.to_add, "variants": len(r.variants),
            "data_pick": {"beats": r.data_pick.beats, "by_pct": round(100 * r.data_pick.by)} if r.data_pick else None}


def loadout_card(s, lo) -> dict:
    return {"key": lo.key, "rank": lo.rank, "kind": "subjugation", "damage": lo.damage, "force": lo.force,
            "decks": [{"phase": d.phase, "title": d.name, "strategy": d.strategy, "damage": d.damage, "knockdowns": d.knockdowns,
                       "tiles": s.tiles(d)} for d in lo.decks]}


def _spec_json(spec):
    if spec is None:
        return None
    ref = lambda r: {"uuid": r.uuid, "source": r.source} if r else None
    out = {"costume": ref(spec.costume), "main_weapon": ref(spec.main_weapon), "subs": [ref(x) for x in spec.subs],
           "companion": ref(spec.companion), "memoirs": [ref(x) for x in spec.memoirs], "debris": ref(spec.debris)}
    if spec.karma:
        out["karma"] = {str(k): int(v) for k, v in spec.karma.items()}     # the Force list's karma (bunker_deckwrite.go)
    return out


# ---------------------------------------------------------------- routes

# ---------------------------------------------------------------- portraits

def _portrait_source():
    """(assetbundle folder's parent, convert) for the game files the player
    imported, converting like the Archive (the Go library: through Java on
    Android, in process on iOS); None without game files or a converter."""
    import android_archive
    revision = android_archive.revision_root(Path(config.ASSETS_DIR).parent)
    if not (revision / "assetbundle").is_dir():
        return None
    try:
        import ios_runtime
        convert = ios_runtime._archive_converters()["decode"]
    except ImportError:
        try:
            convert = android_archive.android_converters()["decode"]
        except ImportError:
            return None
    return revision, convert


def _portrait_cache():
    return Path(config.GAME_DB_PATH).parent / "deckbuilder" / "portraits"


def _costume_asset(costume_id):
    """The costume's art folder name (ch013012), from the game's names."""
    r = runtime.read_json(Path(config.NAMES_DIR) / "costumes.json") or {}
    for rec in r.get("records", []) if isinstance(r, dict) else []:
        if rec.get("id") == costume_id:
            return rec.get("costume_actor_asset_id")
    return None


_portraits = {}


def _game_png(path):
    """A picture from the game's own files, converted like the Archive's (thumb size), made once, then kept."""
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    source = _portrait_source()
    if source is None or not path:
        raise HTTPException(404)
    revision, convert = source
    from archive.media import Textures
    key = (str(revision), str(_portrait_cache()))
    if key not in _portraits:
        _portraits.clear()
        _portraits[key] = Textures(revision / "assetbundle", _portrait_cache(), convert)
    try:
        png = _portraits[key].png(path, "thumb")
    except (FileNotFoundError, ValueError):
        raise HTTPException(404)
    return FileResponse(png, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


@router.get("/decks/portrait/{costume_id}.png")
def portrait(costume_id: int):
    """A costume's portrait from the game's own files."""
    asset = _costume_asset(costume_id)
    return _game_png(asset and f"ui/costume/{asset}/{asset}_portrait.assetbundle")


ICON_KINDS = ("weapon", "companion", "memoir", "debris")


def _icon_asset(kind, piece_id):
    tables = _tables_for(runtime.fingerprint(config.find_master_data_bin()))
    return tables.icon_asset(kind, piece_id)


@router.get("/decks/icon/{kind}/{piece_id}.png")
def icon(kind: str, piece_id: int):
    """A piece's icon from the game's own files, as the game's notices show it."""
    return _game_png(_icon_asset(kind, piece_id) if kind in ICON_KINDS else None)


def _not_ready(exc: StageNotReady, against=None):
    return JSONResponse({"ok": False, "prepare": True, "against": against if exc.extra else None,
                         "costumes": list(exc.extra), "error": str(exc)}, status_code=409)


@router.get("/decks")
def page(request: Request, user: int = 0):
    user_id = _user(user)
    try:
        s = session(user_id)
    except StageNotReady:
        return templates.TemplateResponse(request, "deck_builder.html", {"active": "decks", "user": user_id, "players": [],
                                                                         "slots": [], "opponents": [], "bosses": [], "preparing": True})
    refresh_arena(user_id)
    return templates.TemplateResponse(request, "deck_builder.html", {"active": "decks", "user": user_id, "players": s.players(),
                                                                     "slots": s.slots(), "opponents": s.opponents(), "bosses": s.bosses(),
                                                                     "preparing": False})


@router.post("/decks/prepare")
def prepare_route(payload: dict = Body(default={})):
    """Builds the staging save. Not the player's save: the game plays on."""
    try:
        prepare(_user(payload.get("user")), payload.get("against"), payload.get("costumes") or ())
    except (DeckBuilderError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True}, headers={"x-bunker-keep-playing": "1"})


@router.get("/decks/results")
def results(request: Request, user: int = 0, offset: int = 0, limit: int = 6):
    q = dict(request.query_params)
    def run(s):
        if q.get("deck_for") == "subjugation":
            items = s.subjugation(int(q.get("boss") or 1), int(q.get("difficulty") or 5), criteria_from(None, q)) if offset <= 0 else []
            return {"total": len(items), "items": [loadout_card(s, lo) for lo in items], "exhausted": True, "relax": None}
        p = s.page(criteria_from(s, q), max(0, offset), max(1, min(limit, 24)))
        return {"total": p.total, "items": [card(s, r) for r in p.items], "exhausted": p.exhausted, "relax": p.relax}
    try:
        return _retrying(_user(user), run)
    except StageNotReady as exc:
        return _not_ready(exc, q.get("against"))


@router.get("/decks/detail")
def detail(key: str, user: int = 0):
    try:
        s = session(_user(user))
    except StageNotReady as exc:
        return _not_ready(exc)
    lo = s.find_loadout(key)
    if lo is not None:
        return s.loadout_detail(lo)
    r = s.find(key)
    if r is None:
        return JSONResponse({"ok": False, "error": "That deck is no longer listed"}, status_code=404)
    return s.detail(r)


@router.get("/decks/rescore")
def rescore(request: Request, key: str, user: int = 0):
    """Force and win % with only the ticked costumes raised (?raise=id,id)."""
    try:
        s = session(_user(user))
    except StageNotReady as exc:
        return _not_ready(exc)
    raises = sorted(_ints(request.query_params.get("raise", "")))
    lo = s.find_loadout(key)
    if lo is not None:
        return {"force": sum(s.loadout_force(lo, raises)), "damage": lo.damage}
    r = s.find(key)
    if r is None:
        return JSONResponse({"ok": False, "error": "That deck is no longer listed"}, status_code=404)
    return s.rescore(r, raises)


@router.get("/decks/costumes")
def costumes(user: int = 0, mode: str = "best"):
    try:
        return session(_user(user)).costumes(mode)
    except StageNotReady as exc:
        return _not_ready(exc)


@router.get("/decks/opponents")
def opponents(user: int = 0):
    return session(_user(user)).opponents()


@router.post("/decks/write")
def write(payload: dict = Body(...)):
    refuse = lambda message: JSONResponse({"ok": False, "error": message}, status_code=400)
    try:
        user_id = _user(payload.get("user"))
    except (TypeError, ValueError):
        return refuse("Unknown player")
    try:
        s = session(user_id)
    except StageNotReady as exc:
        return _not_ready(exc)
    lo = s.find_loadout(str(payload.get("key") or ""))
    if lo is not None:
        return _write_loadout(s, user_id, lo, payload.get("raise") or [])
    r = s.find(str(payload.get("key") or ""))
    if r is None:
        return JSONResponse({"ok": False, "error": "That deck is no longer listed"}, status_code=404)
    from deckbuilder.model import ARENA_DECKS, QUEST, QUEST_DECKS
    slots = payload.get("slots") or []
    if not slots:
        return refuse("Choose a deck slot to write to")
    counts = {ARENA: ARENA_DECKS, QUEST: QUEST_DECKS}
    targets = []
    for x in slots:      # an Arena deck number, or {deck_type, number} (Arena or Loadout)
        t, n = (ARENA, x) if isinstance(x, int) and not isinstance(x, bool) else \
            ((x.get("deck_type"), x.get("number")) if isinstance(x, dict) else (None, None))
        if t not in counts or not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= counts[t]:
            return refuse(f"Deck slots are Arena or Loadout decks 1 to {ARENA_DECKS}")
        if (t, n) not in targets:
            targets.append((t, n))
    raises = payload.get("raise") or []
    if not all(isinstance(x, int) for x in raises) or not set(raises) <= s.raisable(r):
        return refuse("Only a costume of this deck that is not fully raised can be raised")
    raises = sorted(set(raises))
    force = s.force(r, raises)
    deck = {"slots": [{"deck_type": t, "number": n, "power": force} for t, n in targets],
            "characters": [_spec_json(x) for x in r.equipped.specs], "raise": raises}
    try:
        _backup()
        _shim({"action": "deck_write", "user_id": user_id, "deck": deck})
    except (DeckBuilderError, ValueError, FileNotFoundError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    drop_session(user_id)                   # the save changed: read it again
    if any(t == ARENA for t, _ in targets):
        refresh_arena(user_id)
    return {"ok": True, "added": s.gen.added(r.equipped.to_add), "raised": raises,
            "slots": [{"deck_type": t, "number": n} for t, n in targets]}


SUBJUGATION = 5     # the game's Subjugation decks: 101, 102, 103 (one per phase)


def _write_loadout(s, user_id, lo, raises):
    """A Subjugation loadout: one Save Data snapshot, then each deck to its Subjugation deck, its own raises only."""
    refuse = lambda message: JSONResponse({"ok": False, "error": message}, status_code=400)
    if not all(isinstance(x, int) for x in raises) or not set(raises) <= s.loadout_raisable(lo):
        return refuse("Only a costume of this loadout that is not fully raised can be raised")
    raises = sorted(set(raises))
    forces = s.loadout_force(lo, raises)
    try:
        _backup()
        for d, force in zip(lo.decks, forces):
            deck = {"slots": [{"deck_type": SUBJUGATION, "number": 100 + d.phase, "power": force}],
                    "characters": [_spec_json(x) for x in d.equipped.specs], "raise": [c for c in raises if c in d.lineup]}
            _shim({"action": "deck_write", "user_id": user_id, "deck": deck})
    except (DeckBuilderError, ValueError, FileNotFoundError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    drop_session(user_id)
    return {"ok": True, "added": sum(s.gen.added(d.equipped.to_add) for d in lo.decks), "raised": raises,
            "slots": [100 + d.phase for d in lo.decks]}
