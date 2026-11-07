"""All maxed's pool, chosen by strength.

Every playable costume is checked the same way: fully raised (level 100, four limit
breaks, five awakenings) with its top-ranked main weapon, three of it in a deck,
against reference decks built the same way (the experts' strongest costume of each
element), over both openings. Built in memory from the master data, nothing staged,
so all of them can be checked (a few seconds). Companions, memoirs, debris, the
Mythic Slab and awakening bonuses are left out for every costume alike, and three of
one costume counts its team effects three times: a screen to choose which costumes
the full search combines, not a ranking of decks.

The pool is the strongest, with at most a few costumes per character (a deck fields a
character once).
"""
from __future__ import annotations

import sqlite3
import uuid as uuid_mod
from typing import NamedTuple

from deckbuilder import equip, model, sim

ELEMENTS = ("fire", "water", "wind", "light", "dark")


class Strength(NamedTuple):
    costume_id: int
    win: float          # against the reference decks, both openings
    margin: float       # HP share left minus the reference's, averaged


def _deck(costume_id, schema, tables, can_awaken) -> model.Deck:
    con = sqlite3.connect(":memory:", check_same_thread=False)
    for t in model.TABLES:
        sql = schema.table_sql(t)
        if sql:
            con.execute(sql)
    uid = schema.uid
    tc = dict(schema.one("select * from user_costumes where user_id=? limit 1"))
    tw = schema.one("select * from user_weapons where user_id=? limit 1")
    weapons = equip.main_candidates(equip.element_of(costume_id, tables), equip._weapon_type(costume_id, tables))
    specs = []
    for _ in range(3):
        c = dict(tc, user_costume_uuid=str(uuid_mod.uuid4()), costume_id=costume_id, level=100, limit_break_count=4, awaken_count=5)
        model._insert(con, "user_costumes", [c])
        w = None
        if weapons and tw:
            w = dict(tw, user_weapon_uuid=str(uuid_mod.uuid4()), weapon_id=weapons[0],
                     level=100 if weapons[0] in can_awaken else 90, limit_break_count=4)
            model._insert(con, "user_weapons", [w])
        specs.append(model.CharacterSpec(model.PieceRef("costume", c["user_costume_uuid"], "save"),
                                         model.PieceRef("weapon", w["user_weapon_uuid"], "save") if w else None, [], None, [], None))
    model._write_deck(con, uid, specs, 2, 1)
    return model.Deck(model.Save(con, uid), 2, 1)


def strength(tables, experts, schema) -> list[Strength]:
    """Every playable costume, strongest first. schema: any save (its tables are copied, not its rows)."""
    sim.use(tables)
    can_awaken = {r["WeaponId"] for r in tables.T("WeaponAwaken")}
    playable = sorted(c for c in tables.idx("Costume", "CostumeId") if tables.is_fieldable(c))
    refs = []
    for e in ELEMENTS:
        best = max((c for c in experts.costumes() if c in playable and equip.element_of(c, tables) == e),
                   key=lambda c: experts.weight(c), default=None)
        if best is not None:
            refs.append(_deck(best, schema, tables, can_awaken))
    out = []
    for cid in playable:
        try:
            d = _deck(cid, schema, tables, can_awaken)
            scores = [sim.score(d, r, tables, runs=1) for r in refs]
        except (IndexError, KeyError, TypeError):
            continue        # a costume the data cannot field (no active skill)
        n = len(scores) or 1
        out.append(Strength(cid, round(sum(s[0] for s in scores) / n, 4), round(sum(s[1] for s in scores) / n, 4)))
    out.sort(key=lambda s: (-s.win, -s.margin, s.costume_id))
    return out


def pool_by_strength(ranked, tables, size=60, per_character=3) -> list[int]:
    costume = tables.idx("Costume", "CostumeId")
    counts, pool = {}, []
    for s in ranked:
        ch = costume[s.costume_id]["CharacterId"]
        if counts.get(ch, 0) >= per_character:
            continue
        counts[ch] = counts.get(ch, 0) + 1
        pool.append(s.costume_id)
        if len(pool) >= size:
            break
    return pool
