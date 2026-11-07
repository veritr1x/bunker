#!/usr/bin/env python3
"""Deck Builder: cached fighters (deckbuilder/fighters.py). Each costume's fighter is built once from its loadout;
a deck's fighters are assembled from the cache, its party-wide statuses shared as the client shares them
(power.actors_for). They must equal building the whole deck, exactly, and fight the same."""
import itertools
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, cli_invoke, needs_stage, tables
from deckbuilder import equip, experts, fighters, model, sim, stage

LINEUPS = [(35036, 33029, 34048), (31032, 32035, 34040), (32028, 31029, 34047), (35035, 34012, 34010)]


@needs_stage
class FighterCacheTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.ex = experts.Experts.load(tables())
        stage.Stager(cli_invoke(path), tables()).build(**equip.stage_plan(LINEUPS, tables(), cls.ex, extra_sets=[17]))
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        sim.use(tables())
        cls.specs = {}
        for l in LINEUPS:
            eq = equip.equip(l, equip.Mode("best"), cls.stage, cls.stage, tables(), cls.ex)
            cls.specs.update({c: s for c, s in zip(l, eq.specs)})
        # one support with Purity (a party-wide Attack status): the case where teammates change each other's stats
        pk = equip._Picker(cls.stage, cls.stage, tables(), equip.Mode("best"))
        cls.specs[33029] = cls.specs[33029]._replace(memoirs=equip._memoirs(pk, 17, "support", tables()))
        cls.cache = fighters.FighterCache(tables(), cls.stage)
        for c, s in cls.specs.items():
            cls.cache.add(c, s)

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def built(self, lineup):
        from deckbuilder.sim import battle
        deck = model.compose(self.stage, self.stage, [self.specs[c] for c in lineup], 2, 7, tables())
        return battle._side(deck, tables())

    def test_cached_fighters_equal_a_built_deck(self):
        costumes = sorted(self.specs)
        for lineup in list(itertools.permutations(costumes, 3))[:60]:
            self.assertEqual(self.cache.side(lineup), self.built(lineup), lineup)

    def test_cached_force_equals_the_deck_power(self):
        """A deck's Force from the cache equals power.deck_power of the deck built whole (each actor keeps its own
        identity: skill power counts a skill's owner by it)."""
        from deckbuilder import power
        for lineup in list(itertools.permutations(sorted(self.specs), 3))[:40]:
            deck = model.compose(self.stage, self.stage, [self.specs[c] for c in lineup], 2, 7, tables())
            self.assertEqual(self.cache.force(lineup), power.deck_power(deck, tables()).total, lineup)

    def test_party_statuses_reach_the_teammates(self):
        """Some fighters' stats are changed by their teammates (party-wide statuses): the sharing is exercised."""
        stat = lambda t: (t["hp"], t["atk"], t["df"], t["agi"])
        changed = 0
        for lineup in itertools.permutations(sorted(self.specs), 3):
            side = self.cache.side(lineup)
            changed += sum(stat(side[s]) != stat(self.cache._templates[c]) for s, c in zip("LMR", lineup))
        self.assertGreater(changed, 0)

    def test_cached_fighters_fight_the_same(self):
        from deckbuilder.sim import battle
        a, b = (35036, 33029, 34048), (31032, 32035, 34040)
        for manual in (True, False):
            x = battle.Battle(self.cache.side(a), self.cache.side(b), random.Random(0), manual); x.logging = False
            y = battle.Battle(self.built(a), self.built(b), random.Random(0), manual); y.logging = False
            self.assertEqual(x.run(), y.run())


if __name__ == "__main__":
    unittest.main()
