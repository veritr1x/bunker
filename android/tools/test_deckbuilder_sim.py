#!/usr/bin/env python3
"""Deck Builder: the status-aware Arena simulator (deckbuilder/sim)."""
import collections
import csv
import random
import sqlite3
import statistics
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, FIX, cli_invoke, needs_master, needs_stage, tables
from deckbuilder import model, sim, stage


def template(cid=1, elem="fire", gauge_full=False, hp=100000.0):
    from deckbuilder.sim import units
    passives = [dict(op="advance", which="cs", frac=1.0, scope="self_01")] if gauge_full else []
    return dict(cid=cid, name=f"unit {cid}", elem=elem, hp=hp, atk=1000.0, df=1000.0, agi=1000.0, crit=0.1, critdmg=1.5,
                cs=dict(name="cs", gauge=1000, timed=False, ops=[], hits=1, combo=True), wskills=[], comp=None,
                passives=passives, team=collections.Counter(), mods=units.merge_mods([]), na=(1.0, 1))


def status(type_, ben, **kw):
    return dict(op="status", scope="self_01", prob=1, st=dict(type=type_, ben=ben, life=("frames", 1800), **kw))


@needs_master
class MechanicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sim.use(tables())
        from deckbuilder.sim import battle, rules
        cls.battle, cls.rules = battle, rules

    def fight(self, att, dfn):
        return self.battle.Battle(att, dfn, random.Random(0))

    def test_element_coefficients(self):
        adv = self.rules.ADV
        self.assertEqual(adv[("fire", "wind")], 1.2)
        self.assertEqual(adv[("wind", "fire")], 0.8)
        self.assertEqual(adv[("light", "dark")], 1.2)
        self.assertEqual(adv[("dark", "light")], 1.2)
        self.assertNotIn(("fire", "fire"), adv)

    def test_compromise_does_not_remove_active_dauntless(self):
        b = self.fight({"L": template(1)}, {"L": template(2)})
        u = b.sides["D"][0]
        b.apply(u, status(44, True, dauntless=True), None)
        b.apply(u, status(43, False), None)
        self.assertTrue(b.has(u, "dauntless"))           # still on
        u.st = [s for s in u.st if s["p"]["type"] != 44]
        b.apply(u, status(44, True, dauntless=True), None)
        self.assertFalse(b.has(u, "dauntless"))          # a new one is blocked

    def test_crush_is_cleansable(self):
        b = self.fight({"L": template(1)}, {"L": template(2)})
        u = b.sides["D"][0]
        b.apply(u, status(30, False, attr=[(2, "taken", 1.3)]), None)
        b.apply(u, dict(op="cleanse", scope="self_01", kinds=2), None)
        self.assertFalse([s for s in u.st if s["p"]["type"] == 30])

    def test_opening_order_right_left_middle(self):
        att = {s: template(i, gauge_full=True) for i, s in enumerate("LMR", 1)}
        dfn = {s: template(10 + i, gauge_full=True) for i, s in enumerate("LMR", 1)}
        for manual, first in ((True, "A"), (False, "D")):
            self.rules.P["ATTACKER_MANUAL"] = manual
            b = self.fight(att, dfn)
            seen = []
            orig = b.run_ops
            def spy(u, ops, hits, comp_atk=None, b=b, orig=orig):
                if ops is u.t["cs"]["ops"]:
                    seen.append((round(b.t / self.rules.P["FPS"], 2), u.side, u.slot))
                return orig(u, ops, hits, comp_atk)
            b.run_ops = spy
            b.run_opening()
            self.assertEqual(seen[0][0], 3.0)
            self.assertEqual([x[1:] for x in seen[:3]], [(first, "R"), (first, "L"), (first, "M")], manual)
        self.rules.P["ATTACKER_MANUAL"] = True

    def test_combo_multiplier(self):
        c = self.rules.Combo()
        rows = dict(c.table)
        c.count["A"] = 20
        self.assertEqual(c.coef("A"), 2.0)
        c.count["A"] = 6                                  # on-screen COMBO 6 uses the row for 5
        self.assertEqual(c.coef("A"), max(v for lo, v in c.table if lo <= 5))
        c.count["A"] = 1
        self.assertEqual(c.coef("A"), rows.get(0, 1.0))

    def test_cooldown_and_buff_clocks(self):
        b = self.fight({"L": template(1)}, {"L": template(2)})
        u = b.sides["A"][0]
        u.w = [600.0]
        u.bf = [dict(key="Attack", v=0.1, left=300, src=1)]
        b.tick(30)                                        # one second
        self.assertEqual(u.w, [540.0])                    # weapon cooldown: 60 per second (60 fps logic)
        self.assertEqual(u.bf[0]["left"], 270)            # buffs: 30 per second


# The video openings (opening_check.py of the research): attacker deck (L, M, R),
# the observed attacker skill order and the first skill's delay after the battle start.
OBS = [
    ((33032, 32035, 35018), ["R", "M"], 2.0), ((32035, 34048, 35036), ["R"], 1.75), ((32022, 32028, 34048), ["R", "L", "M"], 4.5),
    ((32022, 32028, 34048), ["R", "L", "M"], None), ((32035, 35036, 34039), ["L", "M"], 1.0), ((32035, 34048, 35036), ["L", "M", "R"], 4.0),
    ((32035, 35036, 34039), ["L", "M"], 1.0), ((32035, 35036, 34039), ["L", "M"], 1.0), ((32035, 34048, 35036), ["R", "L", "M"], 0.5),
    ((32035, 34048, 35036), ["R", "L"], 3.0), ((53002, 31032, 31030), ["M"], 5.5), ((53002, 31032, 31030), ["M"], 3.0),
    ((53002, 31032, 31030), ["M"], 3.5), ((31031, 53002, 31032), ["R"], 5.5), ((53002, 33030, 31032), ["M", "R"], 6.0),
    ((31030, 31032, 53002), ["M"], 3.5), ((31030, 31032, 53002), ["M"], 3.0), ((31030, 31032, 53002), ["M"], 2.0),
    ((31030, 31032, 53002), ["M"], 3.0), ((31030, 31032, 53002), ["M"], 3.0), ((53002, 33032, 33030), ["R"], 3.0),
]
DEFENSE = (31032, 35036, 33029)


@needs_stage
class VideoOpeningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        costumes = sorted({c for deck, _, _ in OBS for c in deck} | set(DEFENSE))
        stage.Stager(cli_invoke(path), tables()).build(costume_ids=costumes)
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        sim.use(tables())

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def deck(self, costumes, number):
        specs = [model.CharacterSpec(model.PieceRef("costume", self.stage.pick("costume", costume_id=c), "stage"), None, [], None, [], None)
                 for c in costumes]
        return model.compose(self.stage, self.stage, specs, 2, number, tables())

    def test_opening_matches_video(self):
        from deckbuilder.sim import battle, rules, units
        P = rules.P
        dfn = dict(units.units_for(self.deck(DEFENSE, 2), tables()))
        first_ok, terr = 0, []
        for costumes, seq, t0 in OBS:
            att = dict(units.units_for(self.deck(costumes, 1), tables()))
            b = battle.Battle(att, dfn, random.Random(P["SEED"]))
            events = []
            orig = b.run_ops
            def spy(u, ops, hits, comp_atk=None, b=b, orig=orig):
                if ops is u.t["cs"]["ops"]:
                    events.append((b.t / P["FPS"], u.side, u.slot))
                return orig(u, ops, hits, comp_atk)
            b.run_ops = spy
            b.run_opening()
            a = [(t, s) for t, side, s in events if side == "A"]
            first_ok += bool(a) and a[0][1] == seq[0]
            if t0 is not None and a:
                terr.append(abs(a[0][0] - t0))
        self.assertGreaterEqual(first_ok, 19, f"first attacker skill right in {first_ok}/21")
        self.assertLessEqual(statistics.mean(terr), 1.2 + 0.05, f"mean first-skill timing error {statistics.mean(terr):.2f} s")


if __name__ == "__main__":
    unittest.main()
