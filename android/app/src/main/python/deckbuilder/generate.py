"""The generator: an endless, ranked list of Arena decks for the criteria.

Lineups come expert lineups first, then combinations of the costume pool by
expert weight. Cheap filters (include/exclude, elements excluded, required
effects, strategy) run before a lineup is equipped; minimum stats after.
Ranking is the simulated win rate (against the chosen opponent, or the meta
pool for General best); ties put expert lineups first, so a lineup no expert
picked only ranks above an expert one when its win rate is higher, and then it
says which expert deck it beats and by how much (DataPick).

The first FIRST_BLOCK candidates are evaluated and ranked together; later
candidates are evaluated in blocks of BLOCK and each block is ranked within
itself and appended, so pages already shown never change.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import NamedTuple

from deckbuilder import equip, model, power

FIRST_BLOCK = 48
BLOCK = 24
DEFAULT_POOL = 60
EFFECTS = ("compromise", "cleanse", "revive", "provoke", "dauntless", "indomitable", "from_start")
EFFECT_LABEL = {"compromise": "Compromise", "cleanse": "Cleanse", "revive": "Revive", "provoke": "Provoke",
                "dauntless": "Dauntless", "indomitable": "Indomitable", "from_start": "Usable from start"}
STRATEGIES = ("any", "stall", "burst", "dauntless", "compromise_counter", "tank", "mono")
STRATEGY_NAME = {"compromise_counter": "Compromise counter", "dauntless": "Team Dauntless", "tank": "Tank & provoke",
                 "stall": "Stall", "mono": "Mono-element", "burst": "Burst"}
ADVANTAGE = {("dark", "light"), ("light", "dark"), ("fire", "wind"), ("wind", "water"), ("water", "fire")}


class Criteria(NamedTuple):
    deck_for: str = "attack"                 # "attack" or "defense"
    mode: equip.Mode = equip.Mode("best")
    against: object = None                   # a Deck, or None for General best
    strategy: str = "any"
    elements: tuple = (None, None, None)     # per slot (left, middle, right)
    must_have: frozenset = frozenset()
    include: frozenset = frozenset()
    exclude: frozenset = frozenset()
    exclude_elements: frozenset = frozenset()
    min_stats: dict = {}
    sort: str = "match"                      # "match", "force" or "fewest"


class DataPick(NamedTuple):
    beats: str        # the expert deck it ranks above
    by: float         # win-rate difference


@dataclass
class Result:
    rank: int
    lineup: tuple
    name: str
    expert: bool
    deck: model.Deck
    strategy: str
    win_rate: float
    force: int
    to_add: int
    tags: list
    effects: set
    elements: tuple
    stats: list
    why: str
    equipped: equip.Equipped
    variants: list = field(default_factory=list)
    data_pick: DataPick | None = None


class Page(NamedTuple):
    total: int
    items: list
    exhausted: bool
    relax: str | None


class Generator:
    def __init__(self, tables, experts, base: model.Save, stage: model.Save, pool=None, meta_size=5, runs=4):
        from deckbuilder import sim
        sim.use(tables)
        self.tables, self.experts, self.base, self.stage = tables, experts, base, stage
        self.meta_size, self.runs = meta_size, runs
        self._pool = list(pool) if pool else None
        self._flags = {}
        self._meta = None
        self._cache = {}          # criteria key -> state

    # -------------------------------------------------------------- costumes
    def pool(self, mode) -> list:
        if self._pool:
            return self._pool
        if mode.kind == "owned":
            owned = {r["costume_id"] for r in self.base.q("select costume_id from user_costumes where user_id=?")}
            return sorted((c for c in owned if self.tables.is_playable(c)), key=lambda c: (-self.experts.weight(c), c))
        staged = {r["costume_id"] for r in self.stage.q("select costume_id from user_costumes where user_id=?")}
        ranked = [c for c in self.experts.costumes() if c in staged]
        return ranked[:DEFAULT_POOL] or sorted(staged)[:DEFAULT_POOL]

    def flags(self, costume_id) -> set:
        """The effects a costume's character skill and passives bring."""
        if costume_id not in self._flags:
            from deckbuilder.sim import units
            elem = equip.element_of(costume_id, self.tables)
            t = units.build_unit(costume_id, elem, {"hp": 1, "atk": 1, "df": 1, "agi": 1000, "crit": 0, "critdmg": 1500})
            out = set()
            for o in t["cs"]["ops"] + t["passives"]:
                st = o.get("st") or {}
                ty = st.get("type")
                if ty == 43:
                    out.add("compromise")
                if ty == 44 or st.get("dauntless"):
                    out.add("dauntless")
                if ty == 24 or st.get("provoke"):
                    out.add("provoke")
                if ty == 18 or (st.get("ben") and st.get("taken_mult") is not None):
                    out.add("indomitable")
                if o["op"] == "cleanse":
                    out.add("cleanse")
                if o["op"] == "revive":
                    out.add("revive")
                if o["op"] == "advance" and o.get("which") == "cs" and o.get("frac", 0) >= 1.0:
                    out.add("from_start")
            self._flags[costume_id] = out
        return self._flags[costume_id]

    def lineup_effects(self, lineup) -> set:
        return set().union(*(self.flags(c) for c in lineup))

    def strategies(self, lineup, elements) -> list:
        eff = self.lineup_effects(lineup)
        out = []
        if "compromise" in eff:
            out.append("compromise_counter")
        if "dauntless" in eff:
            out.append("dauntless")
        if "provoke" in eff:
            out.append("tank")
        if eff & {"revive", "indomitable"} and "from_start" not in eff:
            out.append("stall")
        if len(set(elements)) == 1:
            out.append("mono")
        if "from_start" in eff or not out:
            out.append("burst")
        return out

    def order(self, combo) -> tuple:
        """Slot order for a combination: the opener (usable from start) right,
        a support or Dauntless unit in the middle, the rest left."""
        expert = next((l for l in self.experts.lineups() if frozenset(l.costumes) == frozenset(combo)), None)
        if expert:
            return expert.costumes
        rest = sorted(combo, key=lambda c: (-self.experts.weight(c), c))
        right = next((c for c in rest if "from_start" in self.flags(c)), rest[0])
        rest.remove(right)
        mid = next((c for c in rest if equip.role(c, self.experts) == "support" or "dauntless" in self.flags(c)), rest[-1])
        rest.remove(mid)
        return (rest[0], mid, right)

    # -------------------------------------------------------------- enumeration
    def _elements(self, lineup, criteria):
        return tuple(criteria.elements[i] or equip.element_of(c, self.tables) for i, c in enumerate(lineup))

    def _passes(self, lineup, criteria, skip=None) -> bool:
        s = set(lineup)
        if skip != "include" and not set(criteria.include) <= s:
            return False
        if skip != "exclude" and s & set(criteria.exclude):
            return False
        els = self._elements(lineup, criteria)
        if skip != "exclude_elements" and set(els) & set(criteria.exclude_elements):
            return False
        if skip != "must_have" and not set(criteria.must_have) <= self.lineup_effects(lineup):
            return False
        if skip != "strategy" and criteria.strategy != "any" and criteria.strategy not in self.strategies(lineup, els):
            return False
        return True

    def lineups(self, criteria, skip=None):
        """Every candidate lineup once (by costume set): expert lineups first,
        then combinations of the pool by summed expert weight."""
        pool = self.pool(criteria.mode)
        seen = set()
        held = self.base if criteria.mode.kind == "owned" else self.stage
        known = {r["costume_id"] for r in held.q("select costume_id from user_costumes where user_id=?")}
        if self._pool:
            known &= set(self._pool)
        for l in self.experts.lineups():
            key = frozenset(l.costumes)
            if key in seen or not set(l.costumes) <= known:
                continue
            seen.add(key)
            if self._passes(l.costumes, criteria, skip):
                yield l.costumes
        combos = sorted(itertools.combinations(pool, 3), key=lambda c: (-sum(self.experts.weight(x) for x in c), c))
        for c in combos:
            key = frozenset(c)
            if key in seen:
                continue
            seen.add(key)
            lineup = self.order(c)
            if self._passes(lineup, criteria, skip):
                yield lineup

    def total(self, criteria, skip=None) -> int:
        return sum(1 for _ in self.lineups(criteria, skip))

    def relax(self, criteria) -> str | None:
        best = None
        for name in ("must_have", "include", "exclude", "exclude_elements", "strategy"):
            n = self.total(criteria, skip=name)
            if n and (best is None or n > best[0]):
                best = (n, name)
        if best is None and any(criteria.elements):
            return "elements"
        return best[1] if best else None

    # -------------------------------------------------------------- evaluation
    def meta(self):
        if self._meta is None:
            pool = sorted(self.experts.meta_pool(), key=lambda l: -l.weight)[:self.meta_size]
            total = sum(l.weight for l in pool) or 1
            self._meta = [(equip.equip(l.costumes, equip.Mode("best"), self.stage, self.stage, self.tables, self.experts,
                                       expert=l, deck_number=90 + i).deck, l.weight / total, l.name)
                          for i, l in enumerate(pool)]
        return self._meta

    def rate(self, deck, criteria) -> float:
        from deckbuilder import sim
        targets = [(criteria.against, 1.0)] if criteria.against is not None else [(d, w) for d, w, _ in self.meta()]
        r = 0.0
        for t, w in targets:
            if criteria.deck_for == "defense":
                r += w * (1 - sim.win_rate(t, deck, self.tables, runs=self.runs))
            else:
                r += w * sim.win_rate(deck, t, self.tables, runs=self.runs)
        return round(r, 4)

    def evaluate(self, lineup, criteria) -> Result | None:
        expert = next((l for l in self.experts.lineups() if l.costumes == lineup), None)
        els = self._elements(lineup, criteria)
        eq = equip.equip(lineup, criteria.mode, self.base, self.stage, self.tables, self.experts, elements=els, expert=expert,
                         rate=(lambda d: self.rate(d, criteria)) if criteria.against is not None else None)
        _, actors, _ = power.actors_for(eq.deck, self.tables)
        stats = [power.character_stats(a, self.tables) if a else None for a in actors]
        for k, v in (criteria.min_stats or {}).items():
            if any(s is None or s.get(k, 0) < v for s in stats):
                return None
        strategies = self.strategies(lineup, els)
        eff = self.lineup_effects(lineup)
        tags = [EFFECT_LABEL[e] for e in EFFECTS if e in eff][:3]
        if criteria.against is not None:
            theirs = [c for c in criteria.against.characters() if c]
            for mine in els:
                for c in theirs:
                    te = equip.element_of(c.costume.id, self.tables)
                    if (mine, te) in ADVANTAGE and len(tags) < 3:
                        tags.append(f"{mine.title()} vs {te} ×1.2")
                        break
                if len(tags) >= 3:
                    break
        name = expert.name if expert else STRATEGY_NAME[strategies[0]]
        return Result(rank=0, lineup=lineup, name=name, expert=expert is not None, deck=eq.deck, strategy=strategies[0],
                      win_rate=self.rate(eq.deck, criteria), force=power.deck_power(eq.deck, self.tables).total,
                      to_add=len(eq.to_add), tags=tags, effects=eff, elements=els, stats=stats,
                      why=f"{STRATEGY_NAME[strategies[0]]}: {', '.join(EFFECT_LABEL[e] for e in EFFECTS if e in eff) or 'damage'}.",
                      equipped=eq)

    def _sort_key(self, criteria):
        if criteria.sort == "force":
            return lambda r: (-r.force, -r.win_rate, r.lineup)
        if criteria.sort == "fewest":
            return lambda r: (r.to_add, -r.win_rate, r.lineup)
        return lambda r: (-r.win_rate, not r.expert, -r.force, r.lineup)

    def _state(self, criteria):
        key = (criteria.deck_for, criteria.mode, id(criteria.against), criteria.strategy, criteria.elements, criteria.must_have,
               criteria.include, criteria.exclude, criteria.exclude_elements, tuple(sorted((criteria.min_stats or {}).items())), criteria.sort)
        if key not in self._cache:
            self._cache[key] = {"it": self.lineups(criteria), "ranked": [], "done": False, "total": None}
        return self._cache[key]

    def _grow(self, st, criteria, need):
        while len(st["ranked"]) < need and not st["done"]:
            size = FIRST_BLOCK if not st["ranked"] else BLOCK
            block = []
            for lineup in st["it"]:
                r = self.evaluate(lineup, criteria)
                if r is not None:
                    block.append(r)
                if len(block) >= size:
                    break
            else:
                st["done"] = True
            block.sort(key=self._sort_key(criteria))
            self._label(st["ranked"], block)
            st["ranked"].extend(block)

    def _label(self, ranked, block):
        start = len(ranked)
        for i, r in enumerate(block):
            r.rank = start + i + 1
        for i, r in enumerate(block):
            if r.expert:
                continue
            below = [x for x in block[i + 1:] if x.expert]
            if below and r.win_rate > below[0].win_rate:
                r.data_pick = DataPick(below[0].name, round(r.win_rate - below[0].win_rate, 4))

    def page(self, criteria: Criteria, offset: int, limit: int) -> Page:
        st = self._state(criteria)
        if st["total"] is None:
            st["total"] = self.total(criteria)
        if st["total"] == 0:
            return Page(0, [], True, self.relax(criteria))
        self._grow(st, criteria, offset + limit)
        items = st["ranked"][offset:offset + limit]
        for r in items:
            r.variants = [l.costumes for l in self.experts.lineups()
                          if frozenset(l.costumes) == frozenset(r.lineup) and l.costumes != r.lineup]
            r.variants += [v for v in self._orders(r.lineup) if v not in r.variants]
        exhausted = st["done"] and offset + limit >= len(st["ranked"])
        return Page(st["total"], items, exhausted, None)

    def _orders(self, lineup):
        """Other slot orders of the same costumes (folded in as variants)."""
        return [p for p in itertools.permutations(lineup) if p != tuple(lineup)][:5]
