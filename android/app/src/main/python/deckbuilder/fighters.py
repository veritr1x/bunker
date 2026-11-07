"""Cached fighters: each costume's simulator unit built once from its loadout, decks assembled from the cache.

Building a fighter reads the save (the costume, its gear, its character's Mythic Slab, ...) and compiles its skills;
almost all of it depends on the costume and its loadout alone. The one thing teammates change is its stats: the
client hands every actor the other actors' party-wide statuses (power.actors_for, ApplyDeckAbilityStatusList) and
then computes its stats (base_power). So the cache keeps, per costume, its actor and its unit template; a deck's
fighters get the others' party statuses, their stats recomputed by the client's own code, and the template's stat
fields filled from them (units.with_stats). The result equals building the whole deck (tests/test_deckbuilder_fighters).
"""
from __future__ import annotations

from deckbuilder import model, power

SLOTS = ("L", "M", "R")


class FighterCache:
    def __init__(self, tables, stage: model.Save):
        from deckbuilder import sim
        sim.use(tables)
        self.tables, self.stage = tables, stage
        self._actors = {}       # key -> power.Actor (its own statuses; other_status set per deck)
        self._templates = {}    # key -> unit template (stats as built alone)

    def add(self, key, spec):
        """Build the fighter for this loadout (a model.CharacterSpec of stage pieces) under key."""
        from deckbuilder.sim import units
        deck = model.compose(self.stage, self.stage, [spec], 2, 1, self.tables)
        _, actors, _ = power.actors_for(deck, self.tables)
        a = actors[0]
        a.uuid = f"fighter:{key}"     # its own identity: skill power counts a skill's owner by it (every one-character
                                      # deck here gets the same deck-character id)
        self._actors[key] = a
        self._templates[key] = dict(units.units_for(deck, self.tables))["L"]

    def __contains__(self, key):
        return key in self._actors

    def side(self, keys) -> dict:
        """{slot: unit template} for the deck of these keys, left to right, as a built deck would give."""
        from deckbuilder.sim import units
        live = [self._actors[k] for k in keys]
        out = {}
        for slot, k, a in zip(SLOTS, keys, live):
            a.other_status = [st for src in live if src is not a for st in src.ability_status if st["scope"] == 2]
            a.base_power(self.tables)
            out[slot] = units.with_stats(self._templates[k], power.character_stats(a, self.tables))
        return out

    def force(self, keys) -> int:
        """The deck's Force (power.deck_power) from the cached actors, their party statuses shared as in side()."""
        live = [self._actors[k] for k in keys]
        for a in live:
            a.other_status = [st for src in live if src is not a for st in src.ability_status if st["scope"] == 2]
            a.base_power(self.tables)
        total = 0
        for a in live:
            sp = power.actor_skill_power(self.tables, a, live)
            total = power.i32(total + power.i32(a.hp_power + a.atk_power + a.vit_power + sum(sp.values())))
        return total

    def side_force(self, keys):
        """(side(keys), force(keys)) with the stats computed once."""
        from deckbuilder.sim import units
        live = [self._actors[k] for k in keys]
        for a in live:
            a.other_status = [st for src in live if src is not a for st in src.ability_status if st["scope"] == 2]
            a.base_power(self.tables)
        side, total = {}, 0
        for slot, k, a in zip(SLOTS, keys, live):
            side[slot] = units.with_stats(self._templates[k], power.character_stats(a, self.tables))
            sp = power.actor_skill_power(self.tables, a, live)
            total = power.i32(total + power.i32(a.hp_power + a.atk_power + a.vit_power + sum(sp.values())))
        return side, total
