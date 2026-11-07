"""Equipping a lineup: the data picks every piece (weapons, companion, debris,
memoirs) for the lineup the experts chose, and overrules an expert's piece only
when the data backs it (a simulated win rate) and the reason can be stated.

Candidates come from data/rankings.json (the research's static scores), the
pieces themselves from the staging save (fully raised by the server) or, in
"What I own", from the player's save.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, NamedTuple

from deckbuilder import model, raise_

DATA = Path(__file__).resolve().parent / "data" / "rankings.json"
ELEM_ATTR = {"dark": 1, "fire": 2, "light": 3, "water": 5, "wind": 6}
ELEMENTS = tuple(ELEM_ATTR)
# role -> (memoir set, main stats of the three memoirs, sub stats of each)
ROLE_MEMOIRS = {
    "attacker": (10, ("crit_rate", "crit_damage", "attack_pct"), ("crit_rate", "crit_damage", "attack_pct", "attack_pct")),
    "support": (17, ("hp_pct", "defense_pct", "hp_pct"), ("hp_pct", "defense_pct", "hp_pct", "defense_pct")),
}
STAT_LABEL = {"Vitality": "DEF", "Attack": "ATK", "Hp": "HP", "Agility": "agility", "CriticalRatio": "crit rate", "CriticalAttack": "crit damage"}
_rankings = None


def rankings() -> dict:
    global _rankings
    if _rankings is None:
        _rankings = json.loads(DATA.read_text())
    return _rankings


class Mode(NamedTuple):
    kind: str                 # "owned" (What I own) or "best" (All maxed)
    allow_missing: int = 0    # What I own: pieces that may be added, fully raised


@dataclass
class Override:
    costume_id: int
    slot: str
    expert_choice: object
    data_choice: object
    reason: str
    evidence: dict


@dataclass
class Equipped:
    deck: model.Deck
    specs: list
    reasons: dict = field(default_factory=dict)       # (costume_id, slot) -> why
    overrides: list = field(default_factory=list)
    to_add: list = field(default_factory=list)        # PieceRefs taken from the stage


def role(costume_id, experts) -> str:
    r = experts.roles(costume_id)
    if r & {"turret", "agility"}:
        return "attacker"
    if any(x.startswith("support") for x in r):
        return "support"
    return "attacker"


def element_of(costume_id, tables, expert_loadout=None) -> str:
    e = tables.costume_element(costume_id)
    if e:
        return e
    ws = (expert_loadout or {}).get("weapons") or []
    w = tables.idx("Weapon", "WeaponId").get(ws[0]) if ws and ws[0] else None
    return {v: k for k, v in ELEM_ATTR.items()}.get(w["AttributeType"], "dark") if w else "dark"


def _weapon_type(costume_id, tables):
    return tables.idx("Costume", "CostumeId")[costume_id]["SkillfulWeaponType"]


# Element advantage in the Arena (×1.2 to the one it beats, ×0.8 to the one that beats it; dark and light beat each other).
BEATS = {"dark": "light", "light": "dark", "fire": "wind", "wind": "water", "water": "fire"}


def main_weapon_reason(source: str, element: str, owned: bool) -> str:
    """The ⓘ note on a main weapon. source: "ranked" (top of the rankings), "expert" (the experts' loadout)
    or "yours" (the player's own, used instead of adding one); element: the weapon's own."""
    first = {"ranked": f"Top-ranked {element} weapon for this costume's weapon type",
             "expert": "The experts' choice for this costume",
             "yours": "Your best weapon of this costume's weapon type, used instead of adding one"}[source]
    if owned and source != "yours":
        first += "; you own it"
    weak = [k for k, v in BEATS.items() if v == element and BEATS.get(element) != k]
    vs = f"strong against {BEATS[element]}" + (f", weak against {weak[0]}" if weak else "")
    return f"{first}. Makes this character {element} in the Arena: {vs}."


def main_candidates(element, weapon_type):
    w = rankings()["weapons"]
    return [int(k) for k, v in sorted(w.items(), key=lambda kv: -kv[1][2]) if v[0] == element and v[1] == weapon_type]


def sub_candidates(element):
    w = rankings()["weapons"]
    return [int(k) for k, v in sorted(w.items(), key=lambda kv: -kv[1][3]) if v[0] == element]


def companion_candidates(element):
    c = rankings()["companions"]
    return [int(k) for k, v in sorted(c.items(), key=lambda kv: -kv[1][1]) if v[0] == element]


def debris_candidates(element, kind):
    d = rankings()["debris"]
    return [int(k) for k, v in sorted(d.items(), key=lambda kv: -kv[1][2]) if v[0] in (element, None) and v[1] == kind]


def top_sets(tables, n=3, exclude=()):
    """The best-scored memoir sets whose bonus has no drawback for its wearer."""
    ranked = sorted(rankings()["memoir_sets"].items(), key=lambda kv: -kv[1])
    out = []
    for sid, _ in ranked:
        sid = int(sid)
        if sid in exclude or _bonus_drawbacks(sid, tables) or len(set_groups(sid, tables)) < 3:
            continue
        out.append(sid)
        if len(out) == n:
            break
    return out


def set_groups(series_id, tables, n=3):
    return raise_.parts_group_of_set(series_id, tables)[:n]


def memoir_specs(series_id, mains, subs, tables):
    return [raise_.memoir_spec(raise_.top_parts_id(g, tables), main, list(subs), tables)
            for g, main in zip(set_groups(series_id, tables), mains)]


def stage_plan(lineups, tables, experts, extra_sets=(), k=2) -> dict:
    """What the staging save must hold to equip these lineups in any element:
    the costumes, the top weapons, companions and debris of every element, and
    the memoir sets each role uses (plus expert and extra sets)."""
    from deckbuilder import sim
    sim.use(tables)
    costumes = sorted({c for l in lineups for c in l})
    weapons, comps, thoughts, sets = set(), set(), set(), {10, 17, *extra_sets, *top_sets(tables)}
    for c in costumes:
        wt = _weapon_type(c, tables)
        for e in ELEMENTS:
            weapons.update(main_candidates(e, wt)[:k])
    for e in ELEMENTS:
        weapons.update(sub_candidates(e)[:k + 2])
        comps.update(companion_candidates(e)[:k])
        for kind in ("gauge", "weapon_stats", "other"):
            thoughts.update(debris_candidates(e, kind)[:1])
    for l in experts.lineups():
        for lo in (l.loadout or {}).values():
            weapons.update(w for w in lo.get("weapons") or [] if w)
            if lo.get("memoir_set"):
                sets.add(lo["memoir_set"])
            if lo.get("companion"):
                comps.add(lo["companion"])
            if lo.get("debris"):
                thoughts.add(lo["debris"])
    known_w, known_c, known_t = tables.idx("Weapon", "WeaponId"), tables.idx("Companion", "CompanionId"), tables.idx("Thought", "ThoughtId")
    memoirs = [m for s in sorted(sets) for _, mains, subs in ROLE_MEMOIRS.values() for m in memoir_specs(s, mains, subs, tables)]
    return dict(costume_ids=costumes, weapon_ids=sorted(w for w in weapons if w in known_w),
                companion_ids=sorted(c for c in comps if c in known_c), thought_ids=sorted(t for t in thoughts if t in known_t),
                memoirs=memoirs)


# ---------------------------------------------------------------- picking

def _chain(weapon_id, tables) -> list:
    """Every id of a weapon's evolution chain (an owned weapon may be at any step)."""
    for rows in _chains(tables).values():
        if weapon_id in rows:
            return rows
    return [weapon_id]


_CHAINS: dict = {}


def _chains(tables) -> dict:
    key = id(tables)
    if key not in _CHAINS:
        groups = {}
        for r in tables.T("WeaponEvolutionGroup"):
            groups.setdefault(r["WeaponEvolutionGroupId"], []).append((r["EvolutionOrder"], r["WeaponId"]))
        _CHAINS[key] = {g: [w for _, w in sorted(rows)] for g, rows in groups.items()}
    return _CHAINS[key]


def _final_id(weapon_id, tables):
    """The id a weapon has once the server evolves it (the end of its chain)."""
    return _chain(weapon_id, tables)[-1]


class _Picker:
    def __init__(self, base, stage, tables, mode):
        self.base, self.stage, self.tables, self.mode = base, stage, tables, mode
        self.used = set()

    def ref(self, kind, source, **where):
        """A piece matching where from source, one not used yet in this deck. A
        staged weapon, memoir or companion may serve twice (the write adds a
        copy per use); a costume, a debris and any piece the player owns may not."""
        save = self.stage if source == "stage" else self.base
        table, ucol, icol = model.KINDS[kind]
        if kind == "weapon" and source == "save" and "weapon_id" in where:
            chain = _chain(where.pop("weapon_id"), self.tables)
            where_sql = f" and weapon_id in ({','.join('?' * len(chain))})"
            args = list(chain)
        else:
            where_sql, args = "", []
        cond = "".join(f" and {k}=?" for k in where) + where_sql
        order = "level desc, " if kind in ("weapon", "companion", "memoir") else ""
        rows = save.q(f"select {ucol} u from {table} where user_id=?{cond} order by {order}{ucol}", *where.values(), *args)
        for r in rows:
            if (source, r["u"]) not in self.used:
                self.used.add((source, r["u"]))
                return model.PieceRef(kind, r["u"], source)
        if rows and source == "stage" and kind in ("weapon", "memoir", "companion"):
            return model.PieceRef(kind, rows[0]["u"], source)
        return None

    def first(self, kind, ids, id_col, **extra):
        """The first id of the ranked list that the allowed sources hold."""
        sources = ("stage",) if self.mode.kind == "best" else ("save", "stage")
        for src in sources:
            for i in ids:
                fid = _final_id(i, self.tables) if kind == "weapon" else i
                r = self.ref(kind, src, **{id_col: fid}, **extra)
                if r:
                    return r, i
        return None, None


def _owned_weapon_of_type(pick, weapon_type, element, tables):
    """The player's best weapon this costume can main: its own element first."""
    weapons = tables.idx("Weapon", "WeaponId")
    attr = ELEM_ATTR.get(element)
    rows = pick.base.q("select user_weapon_uuid u, weapon_id w, level from user_weapons where user_id=? order by level desc, user_weapon_uuid")
    fits = [r for r in rows if weapons.get(r["w"], {}).get("WeaponType") == weapon_type and ("save", r["u"]) not in pick.used]
    fits.sort(key=lambda r: (weapons[r["w"]]["AttributeType"] != attr, -r["level"]))
    if not fits:
        return None
    pick.used.add(("save", fits[0]["u"]))
    return model.PieceRef("weapon", fits[0]["u"], "save"), fits[0]["w"]


def _bonus_drawbacks(series_id, tables):
    """The stats a memoir set's 3-piece bonus lowers on its wearer, as "DEF −30%"."""
    from deckbuilder.sim import units
    out = []
    for r in tables.T("PartsSeriesBonusAbilityGroup"):
        s = tables.idx("PartsSeries", "PartsSeriesId").get(series_id)
        if not s or r["PartsSeriesBonusAbilityGroupId"] != s["PartsSeriesBonusAbilityGroupId"] or r["SetCount"] != 3:
            continue
        ops, _, _ = units.passive_ops([(r["AbilityId"], r["AbilityLevel"])], "dark")
        for o in ops:
            if o["op"] == "buff" and o["value"] < 0 and o["scope"] == "self_01":
                out.append(f"{STAT_LABEL.get(o['key'], o['key'])} −{round(-o['value'] * 100)}%")
    return out


def _memoirs(pick, series_id, role_name, tables):
    _, mains, _ = ROLE_MEMOIRS[role_name]
    refs = []
    for g, main in zip(set_groups(series_id, tables), mains):
        parts_id = raise_.top_parts_id(g, tables)
        main_id = raise_.main_status_id(*raise_.STATS[main], tables)
        r = pick.ref("memoir", "stage", parts_id=parts_id, parts_status_main_id=main_id)
        if r:
            refs.append(r)
    return refs


def equip(lineup, mode: Mode, base: model.Save, stage: model.Save, tables, experts, target=None,
          rate: Callable | None = None, elements=(None, None, None), expert=None, deck_type=2, deck_number=1) -> Equipped:
    from deckbuilder import sim
    sim.use(tables)
    if rate is None and target is not None:
        rate = lambda deck: sim.win_rate(deck, target, tables)
    loadouts = (expert.loadout or {}) if expert else {}
    pick = _Picker(base, stage, tables, mode)
    specs, reasons, plan = [], {}, []
    for i, c in enumerate(lineup):
        lo = loadouts.get(str(c)) or {}
        e = elements[i] or element_of(c, tables, lo)
        r = role(c, experts)
        costume = pick.ref("costume", "stage" if mode.kind == "best" else "save", costume_id=c) or pick.ref("costume", "stage", costume_id=c)
        wt = _weapon_type(c, tables)
        picked = [w for w in (lo.get("weapons") or [])[:1] if w and rankings()["weapons"].get(str(w), [None])[0] == e]
        main, main_id = pick.first("weapon", picked + main_candidates(e, wt), "weapon_id")
        source = "expert" if main_id is not None and main_id in picked else "ranked"
        if mode.kind == "owned" and (main is None or (main.source == "stage" and mode.allow_missing == 0)):
            mine = _owned_weapon_of_type(pick, wt, e, tables)   # an owned weapon of the type before adding one
            if mine:
                (main, main_id), source = mine, "yours"
        subs_ids = [w for w in sub_candidates(e) if w != main_id]
        subs = []
        for _ in range(2):
            s, sid = pick.first("weapon", subs_ids, "weapon_id")
            if s:
                subs.append(s)
                subs_ids = [w for w in subs_ids if w != sid]
        comp, _ = pick.first("companion", ([lo["companion"]] if lo.get("companion") else []) + companion_candidates(e), "companion_id")
        kind = "gauge" if r == "attacker" else "weapon_stats"
        debris, _ = pick.first("debris", ([lo["debris"]] if lo.get("debris") else []) + debris_candidates(e, kind) + debris_candidates(e, "other"), "thought_id")
        series = lo.get("memoir_set") or ROLE_MEMOIRS[r][0]
        memoirs = _memoirs(pick, series, r, tables)
        specs.append(model.CharacterSpec(costume, main, subs, comp, memoirs, debris))
        plan.append((c, r, series, lo.get("memoir_set")))
        if main is not None:
            attr = tables.idx("Weapon", "WeaponId").get(main_id, {}).get("AttributeType")
            own_e = {v: k for k, v in ELEM_ATTR.items()}.get(attr, e)
            reasons[(c, "main_weapon")] = main_weapon_reason(source, own_e, owned=main.source == "save")
        reasons[(c, "memoirs")] = f"Set {series}: the {'attacker' if r == 'attacker' else 'support'} set, mains {', '.join(ROLE_MEMOIRS[r][1])}."
    if mode.kind == "owned":
        specs = _limit_missing(specs, mode.allow_missing, base, stage, tables)
    deck = model.compose(base, stage, specs, deck_type, deck_number, tables, raise_all=mode.kind == "best")
    overrides = []
    for i, (c, r, series, expert_set) in enumerate(plan):
        default = ROLE_MEMOIRS[r][0]
        if not expert_set or expert_set == default:
            continue
        drawbacks = _bonus_drawbacks(expert_set, tables)
        if not drawbacks or rate is None:
            continue
        r_exp, best = rate(deck), None
        for alt_set in dict.fromkeys([default, *top_sets(tables, exclude={expert_set})]):
            memoirs = _memoirs(_Picker(base, stage, tables, mode), alt_set, r, tables)
            if len(memoirs) < 3:
                continue
            alt_specs = list(specs)
            alt_specs[i] = specs[i]._replace(memoirs=memoirs)
            alt = model.compose(base, stage, alt_specs, deck_type, deck_number, tables, raise_all=mode.kind == "best")
            r_alt = rate(alt)
            if r_alt > r_exp and (best is None or r_alt > best[0]):
                best = (r_alt, alt_set, alt_specs, alt)
        if best:
            r_alt, alt_set, specs, deck = best
            overrides.append(Override(c, "memoirs", expert_set, alt_set,
                                      f"The expert loadout uses memoir set {expert_set}. Its 3-piece bonus also lowers the wearer's "
                                      f"{' and '.join(drawbacks)}, which the expert note doesn't mention; with set {alt_set} the deck "
                                      f"wins {r_alt:.0%} of simulated fights instead of {r_exp:.0%}.",
                                      {"win_rate": {"expert": r_exp, "data": r_alt}, "drawbacks": drawbacks}))
            reasons[(c, "memoirs")] = f"Set {alt_set} (data override of the expert's set {expert_set})."
    return Equipped(deck, specs, reasons, overrides, model.missing_pieces(specs))


def _score(ref, save, tables):
    if ref is None:
        return 0.0
    i = save.piece_id(ref.kind, ref.uuid)
    r = rankings()
    if ref.kind == "weapon":
        return r["weapons"].get(str(i), [0, 0, 0, 0])[2]
    if ref.kind == "companion":
        return r["companions"].get(str(i), [0, 0])[1]
    if ref.kind == "debris":
        return r["debris"].get(str(i), [0, 0, 0])[2]
    return 0.0


def _limit_missing(specs, allow, base, stage, tables):
    """What I own: keep at most `allow` stage pieces, the ones that gain most
    over the player's best owned alternative; the rest fall back to owned
    pieces or stay empty."""
    gains = []
    for i, s in enumerate(specs):
        if s.main_weapon and s.main_weapon.source == "stage":
            gains.append((float("inf"), i, "main_weapon", None))   # every character needs one: it comes first
        for slot in ("companion", "debris"):
            ref = getattr(s, slot)
            if ref and ref.source == "stage":
                gains.append((_score(ref, stage, tables), i, slot, None))
        for n, ref in enumerate(s.subs):
            if ref.source == "stage":
                gains.append((_score(ref, stage, tables), i, "subs", n))
        if s.memoirs and any(m.source == "stage" for m in s.memoirs):
            gains.append((0.5, i, "memoirs", None))     # a memoir set counts as its pieces
    gains.sort(key=lambda g: -g[0])
    keep, budget = set(), allow
    for g in gains:
        cost = len(specs[g[1]].memoirs) if g[2] == "memoirs" else 1
        if cost <= budget or g[2] == "main_weapon":
            keep.add((g[1], g[2], g[3]))
            budget -= cost
    out = []
    for i, s in enumerate(specs):
        d = s._asdict()
        for slot in ("main_weapon", "companion", "debris"):
            if d[slot] and d[slot].source == "stage" and (i, slot, None) not in keep:
                d[slot] = None
        d["subs"] = [r for n, r in enumerate(s.subs) if r.source != "stage" or (i, "subs", n) in keep]
        if (i, "memoirs", None) not in keep:
            d["memoirs"] = [m for m in s.memoirs if m.source != "stage"]
        out.append(model.CharacterSpec(**d))
    return out
