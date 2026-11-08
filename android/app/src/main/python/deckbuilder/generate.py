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
CACHE_SIZE = 8          # criteria kept with their ranked results
MIN_STATS_SCAN = 240    # candidates tried before saying no deck meets the minimum stats
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
    beats: str        # the name of the expert deck it ranks above
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
    margin: float = 0.0          # HP share left minus the opponents', averaged (sim.score): orders decks with equal win rates


class Page(NamedTuple):
    total: int
    items: list
    exhausted: bool
    relax: str | None


_FLAGS: dict = {}
OUTSIDERS = 15


def default_pool(tables, experts, size=DEFAULT_POOL, outsiders=OUTSIDERS) -> list:
    """The costumes All maxed combines: the expert picks, and the
    best-scored costumes no expert listed (so the data can find what they missed)."""
    playable = lambda c: tables.is_playable(c) and c in tables.idx("Costume", "CostumeId")
    picks = [c for c in experts.costumes() if playable(c)][:size - outsiders]
    scores = equip.rankings().get("costumes", {})
    others = [int(k) for k, _ in sorted(scores.items(), key=lambda kv: -kv[1])
              if experts.weight(int(k)) == 0 and playable(int(k))][:outsiders]
    return picks + others


def costume_flags(costume_id, tables) -> set:
    """The effects a costume's character skill and passives bring."""
    key = (id(tables), costume_id)
    if key not in _FLAGS:
        from deckbuilder import sim
        sim.use(tables)
        from deckbuilder.sim import units
        elem = equip.element_of(costume_id, tables)
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
        _FLAGS[key] = out
    return _FLAGS[key]


class Generator:
    def __init__(self, tables, experts, base: model.Save, stage: model.Save, pool=None, meta_size=5, runs=4, best_pool=None,
                 baked=None):
        from deckbuilder import sim
        sim.use(tables)
        self.tables, self.experts, self.base, self.stage = tables, experts, base, stage
        self.meta_size, self.runs = meta_size, runs
        self._pool = list(pool) if pool else None
        self._best_pool = list(best_pool) if best_pool else None     # All maxed's pool, chosen by strength (screen)
        self._baked = baked           # deckbuilder.baked.Baked: All maxed against the general meta, baked at build time
        self._baked_lists = {}
        self._baked_results = {}
        self._meta = None
        self._cache = {}          # criteria key -> state

    # -------------------------------------------------------------- costumes
    def pool(self, mode) -> list:
        if self._pool:
            return self._pool
        if mode.kind == "owned":
            owned = {r["costume_id"] for r in self.base.q("select costume_id from user_costumes where user_id=?")}
            scores = equip.rankings().get("costumes", {})
            ranked = sorted((c for c in owned if self.tables.is_playable(c) and c in self.tables.idx("Costume", "CostumeId")),
                            key=lambda c: (-self.experts.weight(c), -scores.get(str(c), 0), c))
            return ranked[:DEFAULT_POOL]
        staged = {r["costume_id"] for r in self.stage.q("select costume_id from user_costumes where user_id=?")}
        pool = [c for c in (self._best_pool or default_pool(self.tables, self.experts)) if c in staged]
        return pool or sorted(staged)[:DEFAULT_POOL]

    def flags(self, costume_id) -> set:
        return costume_flags(costume_id, self.tables)

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

    def _character(self, costume_id):
        c = self.tables.idx("Costume", "CostumeId").get(costume_id)
        return c["CharacterId"] if c else costume_id

    def _passes(self, lineup, criteria, skip=None) -> bool:
        if len({self._character(c) for c in lineup}) < len(lineup):
            return False        # the game fields a character once per deck
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
        held = self.base if criteria.mode.kind == "owned" else self.stage
        known = {r["costume_id"] for r in held.q("select costume_id from user_costumes where user_id=?")}
        # A required costume from outside the pool (the picker lists every costume) joins it for this search.
        extra = [c for c in sorted(criteria.include) if c in known]
        pool = self.pool(criteria.mode)
        pool = pool + [c for c in extra if c not in pool]
        seen = set()
        if self._pool:
            known &= set(self._pool) | set(extra)
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
    def _expert_meta(self, size):
        """The experts' top size meta decks as (deck, weight, name), weighted by the experts' weights."""
        pool = sorted(self.experts.meta_pool(), key=lambda l: -l.weight)[:size]
        total = sum(l.weight for l in pool) or 1
        return [(equip.equip(l.costumes, equip.Mode("best"), self.stage, self.stage, self.tables, self.experts,
                             expert=l, deck_number=90 + i).deck, l.weight / total, l.name)
                for i, l in enumerate(pool)]

    def meta(self):
        if self._meta is None:
            self._meta = self._expert_meta(self.meta_size)
        return self._meta

    def baked_opponents(self):
        """The opponents the bake scored its decks against (deckbuilder.baked.Baked.meta_decks, meta_top): the experts'
        meta decks in the loadouts the bake equipped them with, and the bake's own strongest decks in their baked
        loadouts, every opponent weighted alike. A bake that names none was scored against meta()."""
        b = self._baked
        if b is None or not (b.meta_decks or b.meta_top):
            return self.meta()
        if getattr(self, "_baked_opp", None) is None:
            from deckbuilder import baked as bk
            opp = [(bk.meta_deck(d, i, self.stage, self.tables), d["weight"], d["name"]) for i, d in enumerate(b.meta_decks)] \
                if b.meta_decks else list(self.meta())
            order = bk.debris_order(b.loadouts)
            for i, lineup in enumerate(b.meta_top):
                specs = [bk.loadout_spec(lo, self.stage, self.tables) for lo in bk.deck_loadouts(lineup, b.loadouts, order)]
                opp.append((model.compose(self.stage, self.stage, specs, 2, 200 + i, self.tables), 0.0,
                            "Bake top " + " · ".join(self.tables.character_name(c) for c in lineup)))
            if b.meta_top:
                opp = [(d, 1 / len(opp), n) for d, _, n in opp]
            self._baked_opp = opp
        return self._baked_opp

    def outcome(self, deck, criteria, opponents=None) -> tuple[float, float]:
        """(win rate, margin) of the deck, weighted over the opponents (meta() unless given as (deck, weight, name);
        both openings; sim.score)."""
        from deckbuilder import sim
        targets = [(criteria.against, 1.0)] if criteria.against is not None else \
            [(d, w) for d, w, _ in (opponents if opponents is not None else self.meta())]
        r = m = 0.0
        for t, w in targets:
            if criteria.deck_for == "defense":
                win, margin = sim.score(t, deck, self.tables, runs=self.runs)
                r += w * (1 - win); m -= w * margin
            else:
                win, margin = sim.score(deck, t, self.tables, runs=self.runs)
                r += w * win; m += w * margin
        return round(r, 4), round(m, 4)

    def rate(self, deck, criteria) -> float:
        return self.outcome(deck, criteria)[0]

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
        # Named by its characters, left to right: what tells two decks apart (expert sources are not names).
        name = " · ".join(self.tables.character_name(c) for c in lineup)
        from deckbuilder.explain import short_reason
        win_rate, margin = self.outcome(eq.deck, criteria)
        return Result(rank=0, lineup=lineup, name=name, expert=expert is not None, deck=eq.deck, strategy=strategies[0],
                      win_rate=win_rate, margin=margin, force=power.deck_power(eq.deck, self.tables).total,
                      to_add=self.added(eq.to_add), tags=tags, effects=eff, elements=els, stats=stats,
                      why=short_reason(strategies[0], els, tags, criteria.against, self.tables),
                      equipped=eq)

    def added(self, staged) -> int:
        """Pieces a write adds: staged ones, except a costume or debris the
        player already owns (the write uses theirs; the game holds one)."""
        n = 0
        for ref in staged:
            if ref.kind in ("costume", "debris"):
                kind_id = {"costume": "costume_id", "debris": "thought_id"}[ref.kind]
                if self.base.pick(ref.kind, **{kind_id: self.stage.piece_id(ref.kind, ref.uuid)}):
                    continue
            n += 1
        return n

    def _sort_key(self, criteria):
        if criteria.sort == "force":
            return lambda r: (-r.force, -r.win_rate, -r.margin, r.lineup)
        if criteria.sort == "fewest":
            return lambda r: (r.to_add, -r.win_rate, -r.margin, r.lineup)
        return lambda r: (-r.win_rate, -r.margin, not r.expert, -r.force, r.lineup)

    def _state(self, criteria):
        key = (criteria.deck_for, criteria.mode, id(criteria.against), criteria.strategy, criteria.elements, criteria.must_have,
               criteria.include, criteria.exclude, criteria.exclude_elements, tuple(sorted((criteria.min_stats or {}).items())), criteria.sort)
        if key not in self._cache:
            while len(self._cache) >= CACHE_SIZE:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = {"it": self.lineups(criteria), "ranked": [], "done": False, "total": None, "scanned": 0}
        return self._cache[key]

    def _grow(self, st, criteria, need):
        while len(st["ranked"]) < need and not st["done"]:
            size = FIRST_BLOCK if not st["ranked"] else BLOCK
            block = []
            for lineup in st["it"]:
                st["scanned"] += 1
                r = self.evaluate(lineup, criteria)
                if r is not None:
                    block.append(r)
                if len(block) >= size:
                    break
                if criteria.min_stats and not st["ranked"] and not block and st["scanned"] >= MIN_STATS_SCAN:
                    st["done"] = True    # nothing meets the minimum stats this far: say so rather than scan on
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

    # -------------------------------------------------------------- baked
    def baked_applies(self, criteria) -> bool:
        """All maxed against the general meta, ranked by match or Force, no minimum stats: what the bake ranked."""
        return (self._baked is not None and criteria.mode.kind == "best" and criteria.against is None
                and criteria.deck_for in ("attack", "defense") and not criteria.min_stats and criteria.sort in ("match", "force"))

    def _baked_passes(self, lineup, els, criteria) -> bool:
        """_passes on a baked deck: its elements are its costumes' baked ones (a slot's element is chosen, not set)."""
        s = set(lineup)
        if not set(criteria.include) <= s or s & set(criteria.exclude):
            return False
        if any(want and want != e for want, e in zip(criteria.elements, els)):
            return False
        if set(els) & set(criteria.exclude_elements):
            return False
        if not set(criteria.must_have) <= self.lineup_effects(lineup):
            return False
        if criteria.strategy != "any" and criteria.strategy not in self.strategies(lineup, els):
            return False
        return True

    def _baked_list(self, criteria) -> list:
        key = (criteria.deck_for, criteria.strategy, criteria.elements, criteria.must_have, criteria.include, criteria.exclude,
               criteria.exclude_elements, criteria.sort)
        if key not in self._baked_lists:
            while len(self._baked_lists) >= CACHE_SIZE:
                self._baked_lists.pop(next(iter(self._baked_lists)))
            los = self._baked.loadouts_for(criteria.sort)
            el = lambda c: los[c]["element"]
            force = criteria.sort == "force" and self._baked.has_force()
            # the Force list (each costume in its Force loadout), else the role's list (fight loadouts)
            src = self._baked.records("force" if force else criteria.deck_for)
            out = [r for r in src if self._baked_passes(r.lineup, tuple(el(c) for c in r.lineup), criteria)]
            if criteria.sort == "force" and not force:
                win = (lambda r: (r.defense_win, r.defense_margin)) if criteria.deck_for == "defense" else (lambda r: (r.attack_win, r.attack_margin))
                out.sort(key=lambda r: (-r.force, tuple(-x for x in win(r)), r.lineup))
            self._baked_lists[key] = out
        return self._baked_lists[key]

    def _baked_result(self, rec, criteria, rank) -> Result:
        """A baked deck as a Result: its baked loadouts (a debris taken twice goes to the next: baked.deck_loadouts),
        built with the player's own costumes raised (All maxed writes them so). Its win rate, margin and Force are the
        bake's, which ranked it (a Force-list deck's win rate is simulated: that gear was never fought)."""
        from deckbuilder import baked as bk
        from deckbuilder.explain import short_reason
        which = self._baked.loadouts_for(criteria.sort)
        k = (rec.lineup, criteria.deck_for, which is self._baked.loadouts)
        if k not in self._baked_results:
            if not hasattr(self, "_baked_order"):
                self._baked_order = {}
            if id(which) not in self._baked_order:
                self._baked_order[id(which)] = bk.debris_order(which)
            los = bk.deck_loadouts(rec.lineup, which, self._baked_order[id(which)])
            specs = [bk.loadout_spec(lo, self.stage, self.tables) for lo in los]
            deck = model.compose(self.base, self.stage, specs, 2, 1, self.tables, raise_all=True)
            to_add = [ref for spec in specs for ref in spec.pieces() if ref and ref.source == "stage"]
            reasons = {}
            for lo, base_lo in zip(los, (which[c] for c in rec.lineup)):
                reasons[(lo["costume_id"], "main_weapon")] = equip.main_weapon_reason(
                    "fights" if which is self._baked.loadouts else "force", lo["element"], owned=False)
                if lo["debris"] != base_lo["debris"]:
                    reasons[(lo["costume_id"], "debris")] = "Its first choice is on another character of this deck (the game holds one)."
            eq = equip.Equipped(deck=deck, specs=specs, reasons=reasons, overrides=[], to_add=to_add)
            els = tuple(lo["element"] for lo in los)
            strategies = self.strategies(rec.lineup, els)
            eff = self.lineup_effects(rec.lineup)
            tags = [EFFECT_LABEL[e] for e in EFFECTS if e in eff][:3]
            _, actors, _ = power.actors_for(deck, self.tables)
            stats = [power.character_stats(a, self.tables) if a else None for a in actors]
            if rec.attack_win or rec.attack_margin or rec.defense_win or rec.defense_margin:
                # the numbers it was ranked by, so the list reads in order (the bake fought it fully raised; a save's
                # own karma and ranks can move a written deck's results a little)
                win, margin = (rec.defense_win, rec.defense_margin) if criteria.deck_for == "defense" else (rec.attack_win, rec.attack_margin)
                force = rec.force
            else:
                # the Force list: its gear was never fought, so simulated against the bake's opponents
                win, margin = self.outcome(deck, criteria, self.baked_opponents())
                force = rec.force
            self._baked_results[k] = Result(
                rank=0, lineup=rec.lineup, name=" · ".join(self.tables.character_name(c) for c in rec.lineup),
                expert=any(l.costumes == rec.lineup for l in self.experts.lineups()), deck=deck, strategy=strategies[0],
                win_rate=win, margin=margin, force=force, to_add=self.added(to_add), tags=tags, effects=eff,
                elements=els, stats=stats, why=short_reason(strategies[0], els, tags, None, self.tables), equipped=eq)
        r = self._baked_results[k]
        r.rank = rank
        return r

    def _baked_page(self, criteria, offset, limit) -> Page:
        lst = self._baked_list(criteria)
        if not lst:
            return Page(0, [], True, self.relax(criteria))
        items = [self._baked_result(r, criteria, offset + i + 1) for i, r in enumerate(lst[offset:offset + limit])]
        for r in items:
            r.variants = []
        return Page(len(lst), items, offset + limit >= len(lst), None)

    def page(self, criteria: Criteria, offset: int, limit: int) -> Page:
        if self.baked_applies(criteria):
            return self._baked_page(criteria, offset, limit)
        st = self._state(criteria)
        if st["total"] is None:
            st["total"] = self.total(criteria)
        if st["total"] == 0:
            return Page(0, [], True, self.relax(criteria))
        self._grow(st, criteria, offset + limit)
        if not st["ranked"] and st["done"]:
            return Page(0, [], True, "min_stats" if criteria.min_stats else self.relax(criteria))
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
