"""All-maxed memoirs, under the original game's rules: any main stat the
master data defines (agility, crit damage and crit rate included, which
Bunker's server never rolls), at +15, with up to four sub stats at their top
(level-12) step. The rows themselves are written by the server's
grant_memoir_batch (deckbuilder/stage.py)."""
from __future__ import annotations

from deckbuilder import power

MAX_LEVEL = 15
# name -> (StatusKindType, StatusCalculationType): kind 1 agility, 2 attack,
# 3 crit damage, 4 crit rate, 6 HP, 7 defense; calc 1 flat (permil for ratios), 2 percent ×10.
STATS = {
    "agility": (1, 1), "attack": (2, 1), "attack_pct": (2, 2), "crit_damage": (3, 1), "crit_rate": (4, 1),
    "hp": (6, 1), "hp_pct": (6, 2), "defense": (7, 1), "defense_pct": (7, 2),
}
MAIN_KINDS = {1: "agility", 2: "attack", 3: "crit_damage", 4: "crit_rate", 6: "hp", 7: "defense"}
# Sub stat values at the level-12 step (the fourth and last growth step).
SUB_TOP = {"attack_pct": 75, "defense_pct": 75, "hp_pct": 75, "crit_rate": 75, "crit_damage": 140, "agility": 75}
MAX_SUBS = 4


def main_status_id(kind: int, calc: int, tables) -> int:
    """The top-rarity PartsStatusMain row for a stat (the last of its four)."""
    rows = [r for r in tables.T("PartsStatusMain") if r["StatusKindType"] == kind and r["StatusCalculationType"] == calc]
    if not rows:
        raise ValueError(f"no memoir main stat of kind {kind}, calculation {calc}")
    return max(rows, key=lambda r: r["PartsStatusMainId"])["PartsStatusMainId"]


def memoir_main_value(main_id: int, level: int, tables) -> int:
    """The main stat's value at a level, as power.parts_power computes it."""
    mn = tables.idx("PartsStatusMain", "PartsStatusMainId")[main_id]
    f = tables.nf(mn["StatusNumericalFunctionId"])
    if not f:
        return mn["StatusChangeInitialValue"]
    return power.i32(power.calc_parameter(f[0], f[1], level) + mn["StatusChangeInitialValue"])


def parts_group_of_set(series_id: int, tables) -> list[int]:
    """The memoir groups (one per memoir picture) of a set (PartsSeries)."""
    return sorted(g["PartsGroupId"] for g in tables.T("PartsGroup") if g["PartsSeriesId"] == series_id)


def top_parts_id(group_id: int, tables) -> int:
    """The highest-rarity memoir of a group."""
    rows = [p for p in tables.T("Parts") if p["PartsGroupId"] == group_id]
    if not rows:
        raise ValueError(f"no memoir in group {group_id}")
    return min(rows, key=lambda p: (-p["RarityType"], p["PartsId"]))["PartsId"]


def memoir_spec(parts_id: int, main: str, subs: list[str], tables) -> dict:
    """A grant_memoir_batch entry: the memoir at +15 with the main and sub stats named."""
    if main not in STATS or STATS[main][0] not in MAIN_KINDS:
        raise ValueError(f"not a memoir main stat: {main}")
    if len(subs) > MAX_SUBS:
        raise ValueError(f"a memoir has at most {MAX_SUBS} sub stats")
    for s in subs:
        if s not in SUB_TOP:
            raise ValueError(f"not a memoir sub stat: {s}")
    part = tables.idx("Parts", "PartsId")[parts_id]
    return {
        "parts_id": parts_id,
        "parts_group_id": part["PartsGroupId"],
        "parts_status_main_id": main_status_id(*STATS[main], tables),
        "level": MAX_LEVEL,
        "subs": [{"slot": i, "lottery_id": 0, "kind_type": STATS[s][0], "calc_type": STATS[s][1], "value": SUB_TOP[s]}
                 for i, s in enumerate(subs, 1)],
    }
