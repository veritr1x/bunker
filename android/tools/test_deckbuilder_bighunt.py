#!/usr/bin/env python3
"""Deck Builder: Subjugation bosses from the game data (deckbuilder/bighunt.py) and the boss phase in the
simulator (sim.subjugation_battle)."""
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, cli_invoke, needs_master, needs_stage, tables
from deckbuilder import bighunt, equip, experts, model, sim, stage

SARAFA, RION, SARYU = 35036, 33029, 34048


@needs_master
class BossDataTest(unittest.TestCase):
    def test_five_bosses_one_per_element(self):
        bosses = bighunt.bosses(tables())
        self.assertEqual([(b.id, b.element, b.name) for b in bosses], [
            (1, "fire", "Fiery Cursed God"), (2, "water", "Soggy Cursed God"), (3, "wind", "Windy Cursed God"),
            (4, "light", "Bright Cursed God"), (5, "dark", "Bleak Cursed God")])

    def test_each_boss_has_five_difficulties_of_three_phases(self):
        fire = bighunt.bosses(tables())[0]
        self.assertEqual(sorted(fire.fights), [1, 2, 3, 4, 5])
        f1 = fire.fights[1]
        self.assertEqual((f1.costume_id, f1.level), (118112101, 70572))
        self.assertEqual(fire.fights[5].costume_id, 118112501)
        self.assertEqual(len(f1.phases), 3)
        p = f1.phases[0]
        self.assertEqual(p.frames, 3600)
        self.assertEqual([(t.at, t.down) for t in p.thresholds], [(6000, False), (12000, True)])
        self.assertEqual((p.thresholds[1].frames, p.thresholds[1].ratio), (1050, 4.0))

    def test_gauge_from_a_hit(self):
        """A hit fills the gauge by its damage bracket, for the skill's hit count (five and more use the five-hit rows)."""
        p = bighunt.bosses(tables())[0].fights[1].phases[0]
        self.assertEqual(p.gauge(1, 10000), 400)              # 40‰ below the first bracket
        self.assertEqual(p.gauge(1, 40000), 1200 + 100)        # bracket 30000: 1200 + 10000 × 10‰
        self.assertEqual(p.gauge(9, 10000), p.gauge(5, 10000))


@needs_stage
class BossFightTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.experts = experts.Experts.load(tables())
        stage.Stager(cli_invoke(path), tables()).build(**equip.stage_plan([(SARAFA, RION, SARYU)], tables(), cls.experts))
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        sim.use(tables())
        cls.party = equip.equip((SARAFA, RION, SARYU), equip.Mode("best"), cls.stage, cls.stage, tables(), cls.experts).deck

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def test_boss_unit(self):
        fight = bighunt.bosses(tables())[0].fights[1]
        b = bighunt.boss_unit(fight, self.stage, tables())
        self.assertEqual(b["elem"], "fire")
        self.assertGreater(b["df"], 10000)

    def test_a_phase_scores_the_damage_dealt(self):
        from deckbuilder.sim import battle
        boss = bighunt.bosses(tables())[0]
        fight = boss.fights[1]
        r = battle.boss_phase(self.party, bighunt.boss_unit(fight, self.stage, tables()), fight.phases[0], tables())
        self.assertGreater(r["damage"], 0)
        self.assertLessEqual(r["t"], 60.0)
        again = battle.boss_phase(self.party, bighunt.boss_unit(fight, self.stage, tables()), fight.phases[0], tables())
        self.assertEqual(r["damage"], again["damage"])

    def test_knockdown_multiplies_damage(self):
        """Damage while the boss is down counts DamageRatio‰ times: a phase whose knock-down comes at once scores more."""
        from deckbuilder.sim import battle
        fight = bighunt.bosses(tables())[0].fights[1]
        boss = bighunt.boss_unit(fight, self.stage, tables())
        p = fight.phases[0]
        early = p._replace(thresholds=[bighunt.Threshold(1, True, 1050, 4.0)])
        never = p._replace(thresholds=[])
        a = battle.boss_phase(self.party, boss, early, tables())
        b = battle.boss_phase(self.party, boss, never, tables())
        self.assertEqual((a["knockdowns"], b["knockdowns"]), (1, 0))
        self.assertGreater(a["damage"], b["damage"])



@needs_stage
class LoadoutTest(unittest.TestCase):
    """The best nine characters for a boss: three decks, no character twice, ranked by the damage of the three
    phases (each deck fights one)."""
    POOL = [35036, 33029, 31032, 32035, 34048, 32028, 34040, 31029, 34047, 35035, 34012, 34010, 34011]

    @classmethod
    def setUpClass(cls):
        from deckbuilder import generate
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.experts = experts.Experts.load(tables())
        stage.Stager(cli_invoke(path), tables()).build(**equip.stage_plan([(c,) for c in cls.POOL], tables(), cls.experts))
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        cls.gen = generate.Generator(tables(), cls.experts, cls.stage, cls.stage, pool=cls.POOL, meta_size=1, runs=1)
        from deckbuilder import subjugation
        cls.loadouts = subjugation.rank(cls.gen, bighunt.boss(tables(), 1), 5, equip.Mode("best"), candidates=40, alternatives=4)

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def test_three_decks_of_nine_different_characters(self):
        self.assertTrue(self.loadouts)
        character = lambda c: tables().idx("Costume", "CostumeId")[c]["CharacterId"]
        for lo in self.loadouts:
            self.assertEqual(len(lo.decks), 3)
            chars = [character(c) for d in lo.decks for c in d.lineup]
            self.assertEqual(len(chars), 9)
            self.assertEqual(len(set(chars)), 9, lo.decks)

    def test_ranked_by_total_damage_of_the_three_phases(self):
        totals = [lo.damage for lo in self.loadouts]
        self.assertEqual(totals, sorted(totals, reverse=True))
        for lo in self.loadouts:
            self.assertEqual(lo.damage, sum(d.damage for d in lo.decks))
            self.assertEqual([d.phase for d in lo.decks], [1, 2, 3])
        self.assertEqual(len({frozenset(d.lineup for d in lo.decks) for lo in self.loadouts}), len(self.loadouts))

    def test_decks_hit_the_bosss_weakness(self):
        """The Fiery Cursed God takes x0.5 from all but water: every deck mains water weapons."""
        for lo in self.loadouts:
            for d in lo.decks:
                self.assertEqual(d.elements, ("water", "water", "water"), d.name)

    def test_the_waves_share_the_knock_down_gauge(self):
        """A wave without a knock-down hands its gauge to the next (the game's rule)."""
        for lo in self.loadouts:
            self.assertEqual(lo.decks[0].gauge_in, 0.0)
            for a, b in zip(lo.decks, lo.decks[1:]):
                self.assertEqual(b.gauge_in, 0.0 if a.knockdowns else a.gauge_out)


if __name__ == "__main__":
    unittest.main()
