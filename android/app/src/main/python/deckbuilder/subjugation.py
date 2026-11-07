"""The best nine characters against a Subjugation boss.

A Subjugation loadout is three decks (the game's Subjugation decks 101-103), one per
phase of the fight, nine characters with none twice. Candidate decks come from the
Arena generator's lineups (expert lineups first, then the pool's combinations), each
equipped as the Arena would and run through one boss phase in the simulator
(sim.boss_phase). Loadouts are built from the strongest decks: each of the top few as
the first deck, then the strongest that shares no character with those already
taken; each deck is then run in its own phase (deck 1 in phase 1, ...), and loadouts
are ranked by the sum.
"""
from __future__ import annotations

from typing import NamedTuple

from deckbuilder import bighunt, equip, generate, power, sim


class BossDeck(NamedTuple):
    lineup: tuple
    name: str
    strategy: str
    elements: tuple
    equipped: object            # equip.Equipped
    deck: object                # model.Deck
    force: int
    phase: int                  # 1..3 (0 while a candidate)
    damage: int
    knockdowns: int
    standing: int               # characters standing at the phase's end


class Loadout(NamedTuple):
    key: str
    rank: int
    boss_id: int
    difficulty: int
    decks: list                 # [BossDeck] for phases 1, 2, 3
    damage: int
    force: int


def _characters(lineup, tables):
    costume = tables.idx("Costume", "CostumeId")
    return {costume[c]["CharacterId"] for c in lineup if c in costume}


def _run(gen, lineup, criteria, unit, fight, phase) -> BossDeck:
    expert = next((l for l in gen.experts.lineups() if l.costumes == lineup), None)
    els = gen._elements(lineup, criteria)
    eq = equip.equip(lineup, criteria.mode, gen.base, gen.stage, gen.tables, gen.experts, elements=els, expert=expert,
                     deck_type=5, deck_number=101 + max(phase - 1, 0))
    r = sim.boss_phase(eq.deck, unit, fight.phases[max(phase - 1, 0)], gen.tables)
    name = " · ".join(gen.tables.character_name(c) for c in lineup)
    strategies = gen.strategies(lineup, els)
    return BossDeck(lineup, name, generate.STRATEGY_NAME.get(strategies[0], strategies[0]), els, eq, eq.deck,
                    power.deck_power(eq.deck, gen.tables).total, phase, r["damage"], r["knockdowns"], r["standing"])


class _Pool:
    """Candidate decks run in phase 1, evaluated as needed: the generator's lineups in its order."""
    def __init__(self, gen, criteria, unit, fight):
        self.gen, self.criteria, self.unit, self.fight = gen, criteria, unit, fight
        self.lineups = gen.lineups(criteria)
        self.done = []              # evaluated, in the generator's order
        self.exhausted = False

    def _next(self):
        for lineup in self.lineups:
            if len(_characters(lineup, self.gen.tables)) == len(lineup):
                d = _run(self.gen, lineup, self.criteria, self.unit, self.fight, 0)
                self.done.append(d)
                return d
        self.exhausted = True
        return None

    def fill(self, n):
        while len(self.done) < n and not self.exhausted:
            self._next()

    def best_without(self, used, look=60):
        """The strongest evaluated deck sharing no character with used, evaluating up to `look` more lineups
        when none of those already run fits."""
        fits = lambda d: not (_characters(d.lineup, self.gen.tables) & used)
        best = max((d for d in self.done if fits(d)), key=lambda d: (d.damage, d.force), default=None)
        tried = 0
        while best is None and tried < look and not self.exhausted:
            d = self._next(); tried += 1
            if d is not None and fits(d):
                best = d
        return best


def rank(gen: generate.Generator, boss: bighunt.Boss, difficulty: int, mode: equip.Mode, candidates: int = 120,
         alternatives: int = 6, criteria: generate.Criteria | None = None) -> list[Loadout]:
    """Up to `alternatives` loadouts against the boss at this difficulty, best first."""
    fight = boss.fights[difficulty]
    unit = bighunt.boss_unit(fight, gen.stage, gen.tables)
    crit = (criteria or generate.Criteria())._replace(mode=mode, against=None, deck_for="attack")
    pool = _Pool(gen, crit, unit, fight)
    pool.fill(candidates)
    starts = sorted(pool.done, key=lambda d: (-d.damage, -d.force, d.lineup))[:alternatives * 2]
    seen, out = set(), []
    for start in starts:
        picked, used = [start], set(_characters(start.lineup, gen.tables))
        while len(picked) < 3:
            d = pool.best_without(used)
            if d is None:
                break
            picked.append(d); used |= _characters(d.lineup, gen.tables)
        if len(picked) < 3:
            continue
        ident = frozenset(d.lineup for d in picked)
        if ident in seen:
            continue
        seen.add(ident)
        decks = [_run(gen, d.lineup, crit, unit, fight, i) for i, d in enumerate(picked, 1)]
        out.append(Loadout("", 0, boss.id, difficulty, decks, sum(d.damage for d in decks), sum(d.force for d in decks)))
    out.sort(key=lambda lo: (-lo.damage, -lo.force, [d.lineup for d in lo.decks]))
    return [lo._replace(rank=i, key=f"b{boss.id}d{difficulty}:" + "|".join(",".join(map(str, d.lineup)) for d in lo.decks))
            for i, lo in enumerate(out[:alternatives], 1)]
