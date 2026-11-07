#!/usr/bin/env python3
"""Deck Builder: explanations (deckbuilder/explain.py)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, cli_invoke, needs_stage, tables
from deckbuilder import equip, experts, explain, generate, model, stage

POOL = [35036, 33029, 31032, 32035, 34048, 32028, 34040, 31029, 34047, 35035]
TOP_DEFENSE = (31032, 35036, 33029)


@needs_stage
class ExplainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.experts = experts.Experts.load(tables())
        lineups = [tuple(POOL[i:i + 3]) for i in range(0, 9, 3)] + [TOP_DEFENSE, tuple(POOL[-3:])]
        stage.Stager(cli_invoke(path), tables()).build(**equip.stage_plan(lineups, tables(), cls.experts, extra_sets=[7]))
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        gen = generate.Generator(tables(), cls.experts, cls.stage, cls.stage, pool=POOL, meta_size=2, runs=2)
        cls.against = equip.equip(TOP_DEFENSE, equip.Mode("best"), cls.stage, cls.stage, tables(), cls.experts, deck_number=99).deck
        cls.results = gen.page(generate.Criteria(against=cls.against), 0, 50).items

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def texts(self, e):
        return [e.title, e.why_short, e.why_long, *e.per_character, *e.per_piece.values(), *e.overrides]

    def test_no_banned_claims(self):
        self.assertGreaterEqual(len(self.results), 50)
        for r in self.results:
            for text in self.texts(explain.explain(r, self.against, tables())):
                for pattern in explain.BANNED_CLAIMS:
                    self.assertIsNone(pattern.search(text), f"{r.lineup}: {text!r}")

    def test_banned_claims_catch_known_wrong_text(self):
        for wrong in ("Compromise removes her Dauntless.", "This blocks her first Dauntless.", "Compromise cancels Dauntless",
                      "Crush can't be cleansed."):
            self.assertTrue(any(p.search(wrong) for p in explain.BANNED_CLAIMS), wrong)

    def test_short_reason_fits(self):
        for r in self.results:
            e = explain.explain(r, self.against, tables())
            self.assertLessEqual(len(e.why_short), 110, e.why_short)
            self.assertTrue(e.why_short)
            self.assertEqual(len(e.per_character), 3)

    def test_override_text_has_evidence(self):
        r = self.results[0]
        ov = equip.Override(34040, "memoirs", 7, 17, "The expert loadout uses memoir set 7. Its 3-piece bonus also lowers the wearer's DEF −30%.",
                            {"win_rate": {"expert": 0.41, "data": 0.57}, "drawbacks": ["DEF −30%"]})
        r.equipped.overrides = [ov]
        e = explain.explain(r, self.against, tables())
        [text] = e.overrides
        self.assertIn("DEF −30%", text)
        self.assertIn("57%", text)
        self.assertIn("41%", text)
        r.equipped.overrides = []

    def test_per_character_lines(self):
        r = next(x for x in self.results if x.lineup == TOP_DEFENSE)
        e = explain.explain(r, self.against, tables(), self.experts)
        sarafa = e.per_character[1]
        self.assertIn("expert pick", sarafa)
        self.assertIn("Dauntless", sarafa)
        self.assertNotIn("Revive", sarafa)          # Marie's, not Sarafa's

    def test_long_reason_matches_the_simulation(self):
        r = self.results[0]
        e = explain.explain(r, self.against, tables())
        self.assertRegex(e.why_long, r"(wins|loses) in \d+ s|time")


if __name__ == "__main__":
    unittest.main()
