"""Decks as Deck Builder holds them.

A deck is always backed by save rows, so the exact Force port
(deckbuilder.power) and the save writer see the same thing:

- a deck already in a save is read where it is (read-only);
- a new deck is composed (compose) in memory from the player's save (the
  base) plus pieces from the staging save, where the server raised them
  (deckbuilder.stage). That is what the writer copies into the player's save:
  the pieces from the stage, the costumes the player ticked to raise, and
  the deck's own rows. Nothing else changes.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid as uuidlib
from dataclasses import dataclass, field
from typing import NamedTuple

# kind -> (table, uuid column, id column)
KINDS = {
    "costume": ("user_costumes", "user_costume_uuid", "costume_id"),
    "weapon": ("user_weapons", "user_weapon_uuid", "weapon_id"),
    "companion": ("user_companions", "user_companion_uuid", "companion_id"),
    "memoir": ("user_parts", "user_parts_uuid", "parts_id"),
    "debris": ("user_thoughts", "user_thought_uuid", "thought_id"),
}
# Rows that belong to a piece, by its uuid column.
DEPENDENTS = {
    "costume": ("user_costume_active_skills", "user_costume_awaken_status_ups", "user_costume_lottery_effects"),
    "weapon": ("user_weapon_skills", "user_weapon_abilities", "user_weapon_awakens"),
    "memoir": ("user_parts_status_subs",),
    "companion": (), "debris": (),
}
# Rows that belong to a character (by character_id): the board and rank.
CHARACTER_TABLES = ("user_characters", "user_character_board_abilities", "user_character_board_status_ups",
                    "user_character_boards", "user_character_rebirths")
DECK_TABLES = ("user_decks", "user_deck_characters", "user_deck_sub_weapons", "user_deck_parts")
# Every table a composed deck carries (those the client's Force reads, and the board/rank rows).
TABLES = tuple(dict.fromkeys(
    [t for t, _, _ in KINDS.values()] + [t for ts in DEPENDENTS.values() for t in ts] + list(CHARACTER_TABLES)
    + list(DECK_TABLES) + ["user_important_items"]))
ARENA = 2           # model.DeckType PvP
ARENA_DECKS = 15    # Arena decks the page offers (the videos show "Arena14")
QUEST = 1           # model.DeckType Quest: the Loadout screen's decks
QUEST_DECKS = 15    # Loadout shows 15
COSTUME_RAISE_FIELDS = ("level", "limit_break_count", "awaken_count", "costume_lottery_effect_unlocked_slot_count")


def connect_ro(path) -> sqlite3.Connection:
    """Open a save read-only. A WAL-mode file with no -shm beside it cannot be
    opened with mode=ro by every SQLite build; then fall back to immutable=1,
    which is exact when no -wal file exists."""
    path = str(path)
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        con.execute("select 1 from sqlite_master limit 1").fetchall()
        return con
    except sqlite3.OperationalError:
        if os.path.exists(path + "-wal") and os.path.getsize(path + "-wal") > 0:
            raise
        return sqlite3.connect(f"file:{path}?immutable=1", uri=True, check_same_thread=False)


def snapshot(path) -> sqlite3.Connection:
    """An in-memory copy of a save, read in one transaction; the file is closed after.
    On a device the game's server writes the save in the same process, and SQLite's
    file locks are per process: a connection kept open there can lose its locks and
    read pages mid-write ("database disk image is malformed")."""
    src = connect_ro(path)
    try:
        dst = sqlite3.connect(":memory:", check_same_thread=False)
        src.backup(dst)
        return dst
    finally:
        src.close()


def rows_to_db(tables: dict) -> sqlite3.Connection:
    """An in-memory save from {table: {"sql": CREATE ..., "rows": [...]}}."""
    con = sqlite3.connect(":memory:", check_same_thread=False)
    for name, t in tables.items():
        con.execute(t["sql"])
        _insert(con, name, t["rows"])
    return con


def _insert(con, table, rows, replace=False):
    if not rows:
        return
    cols = [c for c in rows[0]]
    verb = "insert or replace" if replace else "insert"
    con.executemany(f"{verb} into {table} ({','.join(cols)}) values ({','.join('?' * len(cols))})",
                    [tuple(r[c] for c in cols) for r in rows])


def _columns(con, table) -> list[str]:
    return [r[1] for r in con.execute(f"pragma table_info({table})")]


class Save:
    """One user's rows: q() and one() bind user_id first."""

    def __init__(self, con: sqlite3.Connection, user_id: int):
        self.db = con
        self.db.row_factory = sqlite3.Row
        self.uid = user_id

    def q(self, sql, *a):
        return [dict(r) for r in self.db.execute(sql, (self.uid,) + a)]

    def one(self, sql, *a):
        r = self.q(sql, *a)
        return r[0] if r else None

    def has(self, table) -> bool:
        return self.db.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone() is not None

    def table_sql(self, table) -> str | None:
        r = self.db.execute("select sql from sqlite_master where type='table' and name=?", (table,)).fetchone()
        return r[0] if r else None

    def pick(self, kind, **where) -> str | None:
        """The uuid of the strongest piece of a kind matching where (highest level first)."""
        table, ucol, _ = KINDS[kind]
        cond = "".join(f" and {k}=?" for k in where)
        order = " order by level desc," if "level" in _columns(self.db, table) else " order by"
        r = self.one(f"select {ucol} u from {table} where user_id=?{cond}{order} {ucol}", *where.values())
        return r["u"] if r else None

    def piece_id(self, kind, uuid) -> int | None:
        table, ucol, icol = KINDS[kind]
        r = self.one(f"select {icol} i from {table} where user_id=? and {ucol}=?", uuid)
        return r["i"] if r else None


class PieceRef(NamedTuple):
    kind: str
    uuid: str
    source: str           # "save" (the player's) or "stage"


class CharacterSpec(NamedTuple):
    costume: PieceRef
    main_weapon: PieceRef
    subs: list            # up to two weapon PieceRefs
    companion: PieceRef | None
    memoirs: list         # up to three memoir PieceRefs
    debris: PieceRef | None
    karma: dict | None = None   # {slot: odds number}: this karma instead of the staged costume's (the Force list's)

    def pieces(self):
        yield self.costume
        if self.main_weapon:
            yield self.main_weapon
        yield from self.subs
        if self.companion:
            yield self.companion
        yield from self.memoirs
        if self.debris:
            yield self.debris


@dataclass
class Piece:
    kind: str
    id: int
    uuid: str


@dataclass
class CharacterLoadout:
    costume: Piece
    main_weapon: Piece | None
    subs: list
    companion: Piece | None
    memoirs: list
    debris: Piece | None
    karma: list = field(default_factory=list)


@dataclass
class Deck:
    save: Save
    deck_type: int
    deck_number: int

    @classmethod
    def from_inputs(cls, inputs: dict) -> "Deck":
        con = rows_to_db(inputs["tables"])
        return cls(Save(con, inputs["user_id"]), inputs["deck_type"], inputs["deck_number"])

    @classmethod
    def from_save(cls, db_path, user_id, deck_type, deck_number, tables=None) -> "Deck":
        return cls(Save(connect_ro(db_path), user_id), deck_type, deck_number)

    def _row(self):
        return self.save.one("select * from user_decks where user_id=? and deck_type=? and user_deck_number=?",
                             self.deck_type, self.deck_number)

    def _slots(self):
        d = self._row()
        if not d:
            return [None, None, None]
        out = []
        for i in (1, 2, 3):
            u = d[f"user_deck_character_uuid{i:02d}"]
            dc = self.save.one("select * from user_deck_characters where user_id=? and user_deck_character_uuid=?", u) if u else None
            ok = dc and dc["user_costume_uuid"] and self.save.one(
                "select 1 x from user_costumes where user_id=? and user_costume_uuid=?", dc["user_costume_uuid"])
            out.append(dc if ok else None)
        return out

    def specs(self) -> list:
        """One CharacterSpec per slot (None when empty), every piece from this save."""
        s, out = self.save, []
        for dc in self._slots():
            if dc is None:
                out.append(None)
                continue
            u = dc["user_deck_character_uuid"]
            subs = [r["user_weapon_uuid"] for r in s.q("select * from user_deck_sub_weapons where user_id=? and user_deck_character_uuid=? order by ordinal", u)]
            parts = [r["user_parts_uuid"] for r in s.q("select * from user_deck_parts where user_id=? and user_deck_character_uuid=? order by ordinal", u)]
            ref = lambda kind, x: PieceRef(kind, x, "save") if x else None
            out.append(CharacterSpec(costume=ref("costume", dc["user_costume_uuid"]), main_weapon=ref("weapon", dc["main_user_weapon_uuid"]),
                                     subs=[ref("weapon", x) for x in subs if x], companion=ref("companion", dc["user_companion_uuid"]),
                                     memoirs=[ref("memoir", x) for x in parts if x], debris=ref("debris", dc["user_thought_uuid"])))
        return out

    def characters(self) -> list:
        s, out = self.save, []
        for spec in self.specs():
            if spec is None:
                out.append(None)
                continue
            p = lambda r: Piece(r.kind, s.piece_id(r.kind, r.uuid), r.uuid) if r else None
            karma = [r["odds_number"] for r in s.q("select odds_number from user_costume_lottery_effects where user_id=? and user_costume_uuid=? order by slot_number", spec.costume.uuid)]
            out.append(CharacterLoadout(costume=p(spec.costume), main_weapon=p(spec.main_weapon), subs=[p(x) for x in spec.subs],
                                        companion=p(spec.companion), memoirs=[p(x) for x in spec.memoirs], debris=p(spec.debris), karma=karma))
        return out

    def key(self) -> tuple:
        """What the deck is, slot by slot: costume, weapons, companion, memoirs (with
        their stats) and debris ids. Two decks with the same key are the same deck."""
        s, out = self.save, []
        for c in self.characters():
            if c is None:
                out.append(None)
                continue
            mem = []
            for m in c.memoirs:
                p = s.one("select parts_id, parts_status_main_id from user_parts where user_id=? and user_parts_uuid=?", m.uuid)
                subs = tuple(sorted((r["status_kind_type"], r["status_calculation_type"], r["status_change_value"]) for r in
                                    s.q("select * from user_parts_status_subs where user_id=? and user_parts_uuid=?", m.uuid)))
                mem.append((p["parts_id"], p["parts_status_main_id"], subs))
            out.append((c.costume.id, c.main_weapon.id if c.main_weapon else 0, tuple(sorted(w.id for w in c.subs)),
                        c.companion.id if c.companion else 0, tuple(sorted(mem)), c.debris.id if c.debris else 0, tuple(c.karma)))
        return tuple(out)


# ---------------------------------------------------------------- composing

def _copy_piece(dst, src: Save, ref: PieceRef, uid, new_uuid=None):
    """The piece's row and its dependents from src into dst (as user uid)."""
    table, ucol, _ = KINDS[ref.kind]
    rows = src.q(f"select * from {table} where user_id=? and {ucol}=?", ref.uuid)
    for r in rows:
        r["user_id"] = uid
        if new_uuid:
            r[ucol] = new_uuid
    _insert(dst, table, _fit(dst, table, rows), replace=True)
    for dep in DEPENDENTS[ref.kind]:
        if not src.has(dep):
            continue
        drows = src.q(f"select * from {dep} where user_id=? and {ucol}=?", ref.uuid)
        if new_uuid:
            dst.execute(f"delete from {dep} where user_id=? and {ucol}=?", (uid, new_uuid))
        for r in drows:
            r["user_id"] = uid
            if new_uuid:
                r[ucol] = new_uuid
        _insert(dst, dep, _fit(dst, dep, drows), replace=True)


def character_board_ids(tables, character_id) -> list[int]:
    """The character's Mythic Slab boards (assignment -> category -> group -> board)."""
    cats = {a["CharacterBoardCategoryId"] for a in tables.T("CharacterBoardAssignment") if a["CharacterId"] == character_id}
    groups = {g["CharacterBoardGroupId"] for g in tables.T("CharacterBoardGroup") if g["CharacterBoardCategoryId"] in cats}
    return sorted(b["CharacterBoardId"] for b in tables.T("CharacterBoard") if b["CharacterBoardGroupId"] in groups)


def _copy_character(dst, src: Save, character_id, uid, tables):
    """The character's Mythic Slab and exalt rows from src, replacing dst's; its rank only when dst has
    none (as deck_write: the player's rank stays)."""
    present = lambda t: dst.execute("select 1 from sqlite_master where name=?", (t,)).fetchone() and src.has(t)
    for t in CHARACTER_TABLES:
        if t == "user_character_boards" or not present(t):
            continue
        if t == "user_characters" and dst.execute("select 1 from user_characters where user_id=? and character_id=?",
                                                  (uid, character_id)).fetchone():
            continue
        dst.execute(f"delete from {t} where user_id=? and character_id=?", (uid, character_id))
        rows = src.q(f"select * from {t} where user_id=? and character_id=?", character_id)
        for r in rows:
            r["user_id"] = uid
        _insert(dst, t, _fit(dst, t, rows))
    if present("user_character_boards"):
        for b in character_board_ids(tables, character_id):
            dst.execute("delete from user_character_boards where user_id=? and character_board_id=?", (uid, b))
            rows = src.q("select * from user_character_boards where user_id=? and character_board_id=?", b)
            for r in rows:
                r["user_id"] = uid
            _insert(dst, "user_character_boards", _fit(dst, "user_character_boards", rows))


def _fit(dst, table, rows):
    """Rows cut to the columns dst's table has (saves of other versions)."""
    if not rows:
        return rows
    cols = set(_columns(dst, table))
    return [{k: v for k, v in r.items() if k in cols} for r in rows]


def _costume_character(save: Save, costume_uuid):
    r = save.one("select costume_id from user_costumes where user_id=? and user_costume_uuid=?", costume_uuid)
    return r["costume_id"] if r else None


def compose(base: Save, stage: Save | None, specs: list, deck_type: int, deck_number: int,
            tables, raises: list[int] = (), raise_all: bool = False) -> Deck:
    """A deck in memory: base's rows, plus the stage pieces specs name, plus the
    ticked raises (costume ids), plus the deck at (deck_type, deck_number).
    raise_all (All maxed): every costume of the player's in the deck is raised."""
    con = sqlite3.connect(":memory:", check_same_thread=False)
    uid = base.uid
    for t in TABLES:
        sql = base.table_sql(t) or (stage.table_sql(t) if stage else None)
        if not sql:
            continue
        con.execute(sql)
        if base.has(t):
            _insert(con, t, base.q(f"select * from {t} where user_id=?"))
    src = {"save": base, "stage": stage or base}

    def as_owned(ref):
        """Like deck_write: a staged costume or debris the player owns is theirs
        (the game holds one of each), as it is unless ticked to raise."""
        if ref is None or ref.source != "stage" or src["stage"] is base or ref.kind not in ("costume", "debris"):
            return ref
        mine = base.pick(ref.kind, **{KINDS[ref.kind][2]: src["stage"].piece_id(ref.kind, ref.uuid)})
        return PieceRef(ref.kind, mine, "save") if mine else ref
    specs = [s._replace(costume=as_owned(s.costume), debris=as_owned(s.debris)) if s else None for s in specs]
    if raise_all:
        raises = sorted(set(raises) | set(owned_costumes(specs, base)))
    for spec in specs:
        if spec is None:
            continue
        for ref in spec.pieces():
            if ref.source == "stage" and src["stage"] is not base:
                _copy_piece(con, src["stage"], ref, uid)
                if ref.kind == "costume":
                    cid = _character_id(src["stage"], ref.uuid, tables)
                    if cid and not con.execute("select 1 from user_characters where user_id=? and character_id=?", (uid, cid)).fetchone():
                        _copy_character(con, src["stage"], cid, uid, tables)    # a character new to the player comes fully raised
    if raises and stage is not None:
        for costume_id in raises:
            mine = base.pick("costume", costume_id=costume_id)
            theirs = stage.pick("costume", costume_id=costume_id)
            if not mine or not theirs:
                continue
            _copy_piece(con, stage, PieceRef("costume", theirs, "stage"), uid, new_uuid=mine)
            cid = _character_id(stage, theirs, tables)
            if cid:
                _copy_character(con, stage, cid, uid, tables)
    for spec in specs:
        if spec is not None and spec.karma and spec.costume and spec.costume.source == "stage":
            for slot, odds in spec.karma.items():
                con.execute("update user_costume_lottery_effects set odds_number=? where user_id=? and user_costume_uuid=? and slot_number=?",
                            (int(odds), uid, spec.costume.uuid, int(slot)))
    _write_deck(con, uid, specs, deck_type, deck_number)
    return Deck(Save(con, uid), deck_type, deck_number)


def _character_id(save: Save, costume_uuid, tables):
    costume_id = _costume_character(save, costume_uuid)
    c = tables.idx("Costume", "CostumeId").get(costume_id) if costume_id is not None else None
    return c["CharacterId"] if c else None


def _write_deck(con, uid, specs, deck_type, deck_number):
    key = f"deckbuilder/{uid}/{deck_type}/{deck_number}"
    con.execute("delete from user_decks where user_id=? and deck_type=? and user_deck_number=?", (uid, deck_type, deck_number))
    uuids = []
    for i, spec in enumerate(list(specs) + [None] * (3 - len(specs))):
        if spec is None:
            uuids.append("")
            continue
        u = str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, f"{key}/{i}"))
        uuids.append(u)
        for t in ("user_deck_characters", "user_deck_sub_weapons", "user_deck_parts"):
            con.execute(f"delete from {t} where user_id=? and user_deck_character_uuid=?", (uid, u))
        _insert(con, "user_deck_characters", _fit(con, "user_deck_characters", [{
            "user_id": uid, "user_deck_character_uuid": u, "user_costume_uuid": spec.costume.uuid,
            "main_user_weapon_uuid": spec.main_weapon.uuid if spec.main_weapon else "",
            "user_companion_uuid": spec.companion.uuid if spec.companion else "", "power": 0,
            "user_thought_uuid": spec.debris.uuid if spec.debris else "", "dressup_costume_id": 0, "latest_version": 0}]))
        _insert(con, "user_deck_sub_weapons", _fit(con, "user_deck_sub_weapons", [
            {"user_id": uid, "user_deck_character_uuid": u, "ordinal": n, "user_weapon_uuid": w.uuid} for n, w in enumerate(spec.subs)]))
        _insert(con, "user_deck_parts", _fit(con, "user_deck_parts", [
            {"user_id": uid, "user_deck_character_uuid": u, "ordinal": n, "user_parts_uuid": m.uuid} for n, m in enumerate(spec.memoirs)]))
    _insert(con, "user_decks", _fit(con, "user_decks", [{
        "user_id": uid, "deck_type": deck_type, "user_deck_number": deck_number, "user_deck_character_uuid01": uuids[0],
        "user_deck_character_uuid02": uuids[1], "user_deck_character_uuid03": uuids[2], "name": "", "power": 0, "latest_version": 0}]))


# ---------------------------------------------------------------- the player's side

def missing_pieces(specs) -> list:
    """The pieces a deck takes from the staging save: added on write, fully raised."""
    return [ref for spec in specs if spec for ref in spec.pieces() if ref.source == "stage"]


class RaiseItem(NamedTuple):
    costume_id: int
    field: str
    current: int
    target: int
    used_in: list


class Inventory:
    def __init__(self, save: Save, tables=None):
        self.save = save
        self.tables = tables

    def owned(self, kind, id) -> list:
        table, ucol, icol = KINDS[kind]
        return [r[ucol] for r in self.save.q(f"select {ucol} from {table} where user_id=? and {icol}=?", id)]

    def costume_state(self, costume_id) -> dict | None:
        return self.save.one("select * from user_costumes where user_id=? and costume_id=?", costume_id)

    def decks_using(self, costume_id) -> list:
        """(deck_type, number) of the player's decks with this costume in them."""
        rows = self.save.q("select d.deck_type, d.user_deck_number from user_decks d join user_deck_characters dc"
                           " on dc.user_id=d.user_id and dc.user_deck_character_uuid in"
                           " (d.user_deck_character_uuid01, d.user_deck_character_uuid02, d.user_deck_character_uuid03)"
                           " join user_costumes c on c.user_id=dc.user_id and c.user_costume_uuid=dc.user_costume_uuid"
                           " where d.user_id=? and c.costume_id=? order by 1, 2", costume_id)
        return [(r["deck_type"], r["user_deck_number"]) for r in rows]


def owned_costumes(specs, base: Save) -> list[int]:
    """Costume ids of the deck that are the player's own (a staged one they own counts as theirs)."""
    out = []
    for spec in specs:
        if spec is None or spec.costume is None:
            continue
        cid = base.piece_id("costume", spec.costume.uuid) if spec.costume.source == "save" else None
        if cid is not None and cid not in out:
            out.append(cid)
    return out


def _slab(save: Save, character_id) -> int:
    """How far a character's Mythic Slab is filled: the sum of its board abilities' levels."""
    if not save.has("user_character_board_abilities"):
        return 0
    return save.one("select coalesce(sum(level), 0) n from user_character_board_abilities where user_id=? and character_id=?",
                    character_id)["n"]


def raises_needed(specs, base: Save, stage: Save, inventory: Inventory) -> list:
    """What raising each owned costume of the deck to max would change: one item
    per field below the staged (fully raised) value."""
    out = []
    for spec in specs:
        if spec is None or spec.costume is None:
            continue
        uuid = spec.costume.uuid
        if spec.costume.source == "stage":       # a staged costume the player owns is written as theirs (deck_write)
            uuid = base.pick("costume", costume_id=stage.piece_id("costume", spec.costume.uuid)) if stage is not base else None
            if not uuid:
                continue
        mine = base.one("select * from user_costumes where user_id=? and user_costume_uuid=?", uuid)
        theirs = stage.one("select * from user_costumes where user_id=? and costume_id=?", mine["costume_id"]) if mine else None
        if not theirs:
            continue
        used = inventory.decks_using(mine["costume_id"])
        for f in COSTUME_RAISE_FIELDS:
            if f in mine and f in theirs and mine[f] < theirs[f]:
                out.append(RaiseItem(mine["costume_id"], f, mine[f], theirs[f], used))
        mk = lambda s, u: sum(1 for r in s.q("select odds_number from user_costume_lottery_effects where user_id=? and user_costume_uuid=?", u) if r["odds_number"])
        a, b = mk(base, mine["user_costume_uuid"]), mk(stage, theirs["user_costume_uuid"])
        if a < b:
            out.append(RaiseItem(mine["costume_id"], "karma", a, b, used))
        ch = inventory.tables and inventory.tables.idx("Costume", "CostumeId").get(mine["costume_id"], {}).get("CharacterId")
        if ch:
            a, b = _slab(base, ch), _slab(stage, ch)
            if a < b:
                out.append(RaiseItem(mine["costume_id"], "mythic_slab", a, b, used))
    return out


def deck_summary(deck, tables) -> str | None:
    """"Fio, Saryu, Lars"; a slot whose costume is gone reads "a missing costume"."""
    d = deck._row()
    if not d:
        return None
    names = []
    for i in (1, 2, 3):
        u = d[f"user_deck_character_uuid{i:02d}"]
        if not u:
            continue
        dc = deck.save.one("select user_costume_uuid c from user_deck_characters where user_id=? and user_deck_character_uuid=?", u)
        cid = deck.save.piece_id("costume", dc["c"]) if dc and dc["c"] else None
        names.append(tables.character_name(cid) if cid else "a missing costume")
    return ", ".join(names) if names else None


class Slot(NamedTuple):
    deck_type: int
    number: int
    label: str
    summary: str | None


def slots(save: Save, tables) -> list:
    """The decks the page can write to, with the player's lineup in each: the Arena decks, then the Loadout decks."""
    defense = None
    if save.has("user_bunker_ext"):
        r = save.one("select data from user_bunker_ext where user_id=?")
        if r and r["data"]:
            try:
                defense = (json.loads(r["data"]).get("pvp") or {}).get("defenseDeckNumber")
            except ValueError:
                defense = None
    out = []
    for n in range(1, ARENA_DECKS + 1):
        label = f"Arena deck {n}" + (" (defense)" if n == defense else "")
        out.append(Slot(ARENA, n, label, deck_summary(Deck(save, ARENA, n), tables)))
    for n in range(1, QUEST_DECKS + 1):
        out.append(Slot(QUEST, n, f"Loadout deck {n}", deck_summary(Deck(save, QUEST, n), tables)))
    return out
