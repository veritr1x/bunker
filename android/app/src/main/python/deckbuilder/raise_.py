"""All-maxed memoirs, under the original game's rules: any main stat the
master data defines (agility, crit damage and crit rate included, which
Bunker's server never rolls), at +15, with four sub stats whose rolls stack as
the original game's did (NieR Re[in] Guide, Memoirs: a sub stat starts at up to
2.5% HP/ATK/DEF, 5% crit rate, 6% crit damage or 12 agility, is raised at +3,
+6, +9, +12 and +15, and one sub stat tops out at 12.5% / 25% / 36% / 72), each
memoir at its fullest. The master data
has no sub stat growth (the server rolled them), so the guide's numbers are the
source. The rows themselves are written by the server's grant_memoir_batch
(deckbuilder/stage.py)."""
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
# A main stat by the memoir's place in its set (the original game; NieR Re[in] Guide, gorillawiki, ameblo): the first
# mains ATK, DEF or HP (flat or %), the second may also main crit rate or crit damage, the third may also main agility.
_FIRST_MAINS = {"attack", "attack_pct", "defense", "defense_pct", "hp", "hp_pct"}
MAINS_BY_POSITION = (_FIRST_MAINS, _FIRST_MAINS | {"crit_rate", "crit_damage"}, _FIRST_MAINS | {"agility"})


def main_allowed(main: str, position: int) -> bool:
    """Whether the memoir at this place in its set (0, 1, 2) can main this stat."""
    return 0 <= position < len(MAINS_BY_POSITION) and main in MAINS_BY_POSITION[position]
# A sub stat's best roll (its largest starting value) and its top value, in the save's units (permil of a
# percent stat ×10, so 25 = 2.5%; agility points).
SUB_ROLL = {"attack_pct": 25, "defense_pct": 25, "hp_pct": 25, "crit_rate": 50, "crit_damage": 60, "agility": 12}
SUB_TOP = {"attack_pct": 125, "defense_pct": 125, "hp_pct": 125, "crit_rate": 250, "crit_damage": 360, "agility": 72}
MAX_SUBS = 4
MAX_ROLLS = MAX_SUBS + 5          # each sub stat's first roll, then the raises at +3, +6, +9, +12 and +15
MAX_ROLLS_PER_SUB = 6             # a first roll and all five raises: every sub stat can reach its top (36% = 6 × 6%)


def sub_value(name: str, rolls: int) -> int:
    """A sub stat's value after this many of its best rolls, at most the game's top."""
    return min(SUB_ROLL[name] * rolls, SUB_TOP[name])


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
    """A grant_memoir_batch entry: the memoir at +15 with the main and sub stats named. A sub stat named n times
    has n rolls (in the order first named)."""
    if main not in STATS or STATS[main][0] not in MAIN_KINDS:
        raise ValueError(f"not a memoir main stat: {main}")
    for s in subs:
        if s not in SUB_TOP:
            raise ValueError(f"not a memoir sub stat: {s}")
    rolls = {}
    for s in subs:
        rolls[s] = rolls.get(s, 0) + 1
    if len(rolls) > MAX_SUBS:
        raise ValueError(f"a memoir has at most {MAX_SUBS} sub stats")
    if len(subs) > MAX_ROLLS:
        raise ValueError(f"a memoir has at most {MAX_ROLLS} sub stat rolls")
    if max(rolls.values(), default=0) > MAX_ROLLS_PER_SUB:
        raise ValueError(f"a sub stat has at most {MAX_ROLLS_PER_SUB} rolls")
    part = tables.idx("Parts", "PartsId")[parts_id]
    return {
        "parts_id": parts_id,
        "parts_group_id": part["PartsGroupId"],
        "parts_status_main_id": main_status_id(*STATS[main], tables),
        "level": MAX_LEVEL,
        "subs": [{"slot": i, "lottery_id": 0, "kind_type": STATS[s][0], "calc_type": STATS[s][1], "value": sub_value(s, n)}
                 for i, (s, n) in enumerate(rolls.items(), 1)],
    }
