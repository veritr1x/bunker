"""Deck Builder's decks for the Arena's computer players.

export_table writes bunker_arena_decks.json, which the server's ladder reads
(server/internal/pvp/decktable.go): decks sampled across the whole ranked
range, weak to strong, each with its full loadout (ids), its quality (win
rate against the meta decks, 0-1) and its exact Force, plus a Force-to-quality
curve for players who haven't been scored. score_player rates the player's own
Arena decks the same way, so the ladder scales to deck strength, not Force.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

from deckbuilder import equip, generate, model, power, sim

DECK_FILE = "bunker_arena_decks.json"
PLAYER_FILE = "bunker_arena_players.json"
ARENA = 2


class PlayerScore(NamedTuple):
    attack: float
    defense: float
    power: int


def meta_decks(tables, experts, stage, meta_size=5) -> list:
    """[(deck, weight)] for the strongest meta lineups, weights summing to 1."""
    pool = sorted(experts.meta_pool(), key=lambda l: -l.weight)[:meta_size]
    total = sum(l.weight for l in pool) or 1
    return [(equip.equip(l.costumes, equip.Mode("best"), stage, stage, tables, experts, expert=l, deck_number=90 + i).deck, l.weight / total)
            for i, l in enumerate(pool)]


def _rate(deck, meta, tables, runs, defend=False):
    if defend:
        return round(sum(w * (1 - sim.win_rate(d, deck, tables, runs=runs)) for d, w in meta), 4)
    return round(sum(w * sim.win_rate(deck, d, tables, runs=runs) for d, w in meta), 4)


def character_json(deck) -> list:
    s, out = deck.save, []
    for c in deck.characters():
        if c is None:
            continue
        cos = s.one("select awaken_count from user_costumes where user_id=? and user_costume_uuid=?", c.costume.uuid) or {}
        parts = []
        for m in c.memoirs:
            p = s.one("select parts_id, parts_status_main_id from user_parts where user_id=? and user_parts_uuid=?", m.uuid)
            subs = [[r["status_kind_type"], r["status_calculation_type"], r["status_change_value"]] for r in
                    s.q("select * from user_parts_status_subs where user_id=? and user_parts_uuid=? order by status_index", m.uuid)]
            parts.append({"id": p["parts_id"], "main": p["parts_status_main_id"], "subs": subs})
        out.append({"costume": c.costume.id, "main_weapon": c.main_weapon.id if c.main_weapon else 0,
                    "subs": [w.id for w in c.subs], "companion": c.companion.id if c.companion else 0, "parts": parts,
                    "thought": c.debris.id if c.debris else 0, "karma": c.karma, "awaken": cos.get("awaken_count", 0), "board": True})
    return out


def power_curve(decks, buckets=5) -> list:
    """[[force, quality]] from weak to strong; quality never falls as Force rises."""
    pts = sorted((d["power"], d["quality"]) for d in decks)
    if not pts:
        return []
    n = max(1, len(pts) // buckets)
    curve, best = [], 0.0
    for i in range(0, len(pts), n):
        chunk = pts[i:i + n]
        best = max(best, round(sum(q for _, q in chunk) / len(chunk), 4))
        curve.append([int(sum(p for p, _ in chunk) / len(chunk)), best])
    return curve


def export_table(tables, experts, stage, out: Path, size=300, pool=None, master_sha="", meta_size=5, runs=2) -> None:
    sim.use(tables)
    gen = generate.Generator(tables, experts, stage, stage, pool=pool, meta_size=meta_size, runs=runs)
    criteria = generate.Criteria()
    lineups = list(gen.lineups(criteria))
    step = max(1, len(lineups) / max(1, size))
    picked = [lineups[int(i * step)] for i in range(min(size, len(lineups)))]
    decks = []
    for lineup in picked:
        r = gen.evaluate(lineup, criteria)
        if r is None:
            continue
        decks.append({"quality": r.win_rate, "power": r.force, "lineup": list(lineup), "characters": character_json(r.deck)})
    decks.sort(key=lambda d: (-d["quality"], -d["power"], d["lineup"]))
    data = {"version": 1, "master_sha256": master_sha, "decks": decks, "power_to_quality": power_curve(decks)}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(data, separators=(",", ":")))


def needs_export(path: Path, master_sha: str) -> bool:
    try:
        return json.loads(Path(path).read_text()).get("master_sha256") != master_sha
    except (OSError, ValueError):
        return True


def _defense_number(base) -> int:
    if base.has("user_bunker_ext"):
        r = base.one("select data from user_bunker_ext where user_id=?")
        try:
            n = (json.loads(r["data"]).get("pvp") or {}).get("defenseDeckNumber") if r and r["data"] else None
        except ValueError:
            n = None
        if n:
            return int(n)
    return 1


def score_player(base, tables, experts, stage, meta_size=5, runs=2) -> PlayerScore:
    """The player's best Arena attack deck and their defense deck, rated
    against the meta decks; power is the defense deck's Force."""
    sim.use(tables)
    meta = meta_decks(tables, experts, stage, meta_size)
    numbers = [r["user_deck_number"] for r in base.q("select user_deck_number from user_decks where user_id=? and deck_type=?", ARENA)]
    decks = {n: model.Deck(base, ARENA, n) for n in numbers if any(model.Deck(base, ARENA, n).characters())}
    if not decks:
        return PlayerScore(0.0, 0.0, 0)
    attack = max(_rate(d, meta, tables, runs) for d in decks.values())
    dnum = _defense_number(base)
    defense_deck = decks.get(dnum) or next(iter(decks.values()))
    return PlayerScore(attack, _rate(defense_deck, meta, tables, runs, defend=True), power.deck_power(defense_deck, tables).total)


def write_player_score(path: Path, user_id: int, score: PlayerScore) -> None:
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        data = {}
    data[str(user_id)] = score._asdict()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, sort_keys=True))
