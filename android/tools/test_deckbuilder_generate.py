#!/usr/bin/env python3
"""Deck Builder: the generator (deckbuilder/generate.py)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, cli_invoke, needs_stage, tables
from deckbuilder import equip, experts, generate, model, stage

SARAFA, RION, MARIE, NY_YUDIL, SARYU, SUMMER_YURIE, PHANTASMAL_YUDIL, FESTIVE_FIO, FESTIVE_YURIE, LARS = (
    35036, 33029, 31032, 32035, 34048, 32028, 34040, 31029, 34047, 35035)
POOL = [SARAFA, RION, MARIE, NY_YUDIL, SARYU, SUMMER_YURIE, PHANTASMAL_YUDIL, FESTIVE_FIO, FESTIVE_YURIE, LARS]
TOP_DEFENSE = (MARIE, SARAFA, RION)


@needs_stage
class GenerateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.experts = experts.Experts.load(tables())
        lineups = [tuple(POOL[i:i + 3]) for i in range(0, len(POOL), 3)] + [TOP_DEFENSE]
        stage.Stager(cli_invoke(path), tables()).build(**equip.stage_plan(lineups + [tuple(POOL[-3:])], tables(), cls.experts))
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        cls.gen = generate.Generator(tables(), cls.experts, cls.stage, cls.stage, pool=POOL, meta_size=2, runs=2)
        cls.top_defense = equip.equip(TOP_DEFENSE, equip.Mode("best"), cls.stage, cls.stage, tables(), cls.experts, deck_number=99).deck

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def criteria(self, **kw):
        return generate.Criteria(**dict(dict(deck_for="attack", mode=equip.Mode("best"), against=self.top_defense), **kw))

    def test_generate_ranks_by_win_rate(self):
        page = self.gen.page(self.criteria(), 0, 6)
        self.assertEqual(len(page.items), 6)
        rates = [r.win_rate for r in page.items]
        self.assertEqual(rates, sorted(rates, reverse=True))
        self.assertEqual([r.rank for r in page.items], list(range(1, 7)))
        self.assertTrue(all(r.force > 0 for r in page.items))

    def test_data_pick_reason(self):
        items = self.gen.page(self.criteria(), 0, 30).items
        expert_ranks = [r.rank for r in items if r.expert]
        for r in items:
            if not r.expert and expert_ranks and r.rank < max(expert_ranks):
                self.assertIsNotNone(r.data_pick, r.lineup)
                below = [x for x in items if x.expert and x.rank > r.rank]
                self.assertEqual(r.data_pick.beats, below[0].name)
                self.assertGreater(r.data_pick.by, 0)
            if r.expert:
                self.assertIsNone(r.data_pick)

    def test_filters(self):
        c = self.criteria(elements=(None, None, "water"), must_have=frozenset({"compromise"}), exclude=frozenset({SARAFA}),
                          min_stats={"agi": 1000})
        page = self.gen.page(c, 0, 10)
        self.assertTrue(page.items)
        for r in page.items:
            self.assertNotIn(SARAFA, r.lineup)
            self.assertIn("compromise", r.effects)
            self.assertEqual(r.elements[2], "water")
            self.assertTrue(all(s["agi"] >= 1000 for s in r.stats))

    def test_variants_fold(self):
        items = self.gen.page(self.criteria(), 0, 40).items
        sets = [frozenset(r.lineup) for r in items]
        self.assertEqual(len(sets), len(set(sets)))
        top = [r for r in items if frozenset(r.lineup) == frozenset(TOP_DEFENSE)]
        self.assertTrue(top and top[0].variants)

    def test_paging_stable(self):
        c = self.criteria()
        a = self.gen.page(c, 0, 6).items + self.gen.page(c, 6, 6).items
        b = self.gen.page(c, 0, 12).items
        self.assertEqual([r.lineup for r in a], [r.lineup for r in b])

    def test_generate_no_match(self):
        c = self.criteria(must_have=frozenset({"compromise"}), exclude=frozenset({NY_YUDIL}), elements=("fire", "fire", "fire"))
        page = self.gen.page(c, 0, 6)
        self.assertEqual((page.total, page.items, page.exhausted), (0, [], True))
        self.assertIn(page.relax, ("must_have", "exclude", "elements"))


if __name__ == "__main__":
    unittest.main()
