#!/usr/bin/env python3
"""Deck Builder: the expert data (deckbuilder/experts.py, data/experts.json)."""
import json
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import needs_master, tables
from deckbuilder import experts

SARAFA, NY_YUDIL = 35036, 32035
TOP_DEFENSE = (31032, 35036, 33029)


@needs_master
class ExpertsTest(unittest.TestCase):
    def test_experts_load(self):
        e = experts.Experts.load(tables())
        self.assertEqual(e.weight(SARAFA), 1.0)
        self.assertIn("turret", e.roles(SARAFA))
        self.assertIn("agility", e.roles(NY_YUDIL))
        self.assertEqual(e.weight(10100), 0.0)          # not an expert pick
        self.assertGreaterEqual(len(e.lineups()), 20)
        loaded = [l for l in e.lineups() if l.loadout]
        self.assertTrue(loaded and all(len(l.costumes) == 3 for l in loaded))

    def test_meta_pool_includes_top_defense(self):
        pool = experts.Experts.load(tables()).meta_pool()
        self.assertIn(TOP_DEFENSE, [l.costumes for l in pool])
        self.assertAlmostEqual(sum(l.weight for l in pool), 1.0, places=6)

    def test_experts_unknown_ids_skipped(self):
        data = {"version": 1, "costumes": {"35036": {"weight": 1.0, "roles": ["turret"]}, "99999999": {"weight": 1.0, "roles": ["turret"]}},
                "lineups": [{"name": "ok", "costumes": list(TOP_DEFENSE), "source": "t"},
                            {"name": "gone", "costumes": [99999999, 35036, 33029], "source": "t"}]}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "experts.json"
            path.write_text(json.dumps(data))
            with self.assertLogs("deckbuilder.experts", level="WARNING") as logs:
                e = experts.Experts.load(tables(), path)
        self.assertEqual(e.weight(99999999), 0.0)
        self.assertEqual([l.name for l in e.lineups()], ["ok"])
        self.assertTrue(any("99999999" in m for m in logs.output))


if __name__ == "__main__":
    unittest.main()
