#!/usr/bin/env python3
"""Deck Builder acceptance (design §11): agreement with the experts, the
opening check, and exact Force, on the real engine and data."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, cli_invoke, needs_stage, tables
from deckbuilder import equip, experts, generate, model, stage
import test_deckbuilder_power
import test_deckbuilder_sim


@needs_stage
class AgreementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.experts = experts.Experts.load(tables())
        cls.pool = generate.default_pool(tables(), cls.experts)
        plan = equip.stage_plan([(c,) for c in cls.pool] + [l.costumes for l in cls.experts.lineups()], tables(), cls.experts)
        stage.Stager(cli_invoke(path), tables()).build(**plan)
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def test_pool_holds_non_expert_costumes(self):
        """Otherwise agreement with the experts would hold by construction."""
        non_expert = [c for c in self.pool if self.experts.weight(c) == 0]
        self.assertGreaterEqual(len(non_expert), 10)

    def test_top20_agrees_with_experts(self):
        gen = generate.Generator(tables(), self.experts, self.stage, self.stage, meta_size=3, runs=2)
        seen = []
        offset = 0
        while len(seen) < 20:
            page = gen.page(generate.Criteria(), offset, 12)
            for r in page.items:
                for c in r.lineup:
                    if c not in seen:
                        seen.append(c)
            offset += 12
            if page.exhausted:
                break
        top = seen[:20]
        agree = sum(1 for c in top if self.experts.weight(c) > 0)
        self.assertGreaterEqual(agree, 19, f"{agree}/20 expert picks in {top}")


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(AgreementTest))
    suite.addTests(loader.loadTestsFromTestCase(test_deckbuilder_sim.VideoOpeningTest))
    suite.addTests(loader.loadTestsFromTestCase(test_deckbuilder_power.PowerTest))
    return suite


if __name__ == "__main__":
    unittest.main()
