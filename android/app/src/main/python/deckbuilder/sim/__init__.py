"""The status-aware Arena simulator (ported from the research prototype).

Call use(tables) once with the active master data; it (re)loads the modules
whose indexes are built from it. Then:

    from deckbuilder import sim
    sim.use(tables)
    outcome = sim.simulate(attacker_deck, defender_deck, tables, seed=0)
    rate = sim.win_rate(attacker_deck, defender_deck, tables)
"""
from __future__ import annotations

import importlib

_tables = None
_MODULES = ("data", "status", "rules", "units", "battle", "subjugation_battle")


def _bound():
    if _tables is None:
        raise RuntimeError("deckbuilder.sim.use(tables) first")
    return _tables


_use_lock = __import__("threading").RLock()


def use(tables) -> None:
    with _use_lock:
        _use(tables)


def _use(tables) -> None:
    global _tables
    if _tables is tables:
        return
    _tables = tables
    import sys
    for name in _MODULES:
        full = f"deckbuilder.sim.{name}"
        if full in sys.modules:
            importlib.reload(sys.modules[full])
        else:
            importlib.import_module(full)


def simulate(attacker, defender, tables, seed: int = 0, attacker_manual: bool = True):
    use(tables)
    from deckbuilder.sim import battle
    return battle.simulate(attacker, defender, tables, seed=seed, attacker_manual=attacker_manual)


def score(attacker, defender, tables, runs: int | None = None) -> tuple[float, float]:
    use(tables)
    from deckbuilder.sim import battle
    return battle.score(attacker, defender, tables, runs=runs)


def boss_phase(party, boss, phase, tables, seed: int = 0) -> dict:
    """One Subjugation phase (deckbuilder.bighunt): damage dealt, knock-downs, time lasted."""
    use(tables)
    from deckbuilder.sim import battle
    return battle.boss_phase(party, boss, phase, tables, seed=seed)


def win_rate(attacker, defender, tables, runs: int | None = None) -> float:
    use(tables)
    from deckbuilder.sim import battle
    return battle.win_rate(attacker, defender, tables, runs=runs)
