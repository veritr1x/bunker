#!/usr/bin/env python3
"""Deck Builder → Arena computer players: the deck table and the player's
score (deckbuilder/ladder.py)."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, FIX, cli_invoke, needs_stage, tables
from deckbuilder import equip, experts, ladder, model, power, sim, stage

POOL = [35036, 33029, 31032, 32035, 34048, 32028, 34040, 31029, 34047, 35035]
SNAP = "2d981f327817"     # owns PvP deck 2/1 (197235)


@needs_stage
class LadderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.experts = experts.Experts.load(tables())
        lineups = [(c,) for c in POOL] + [l.costumes for l in cls.experts.lineups()]
        stage.Stager(cli_invoke(path), tables()).build(**equip.stage_plan(lineups, tables(), cls.experts))
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        cls.out = Path(cls.dir.name) / "bunker_arena_decks.json"
        ladder.export_table(tables(), cls.experts, cls.stage, cls.out, size=16, pool=POOL, master_sha="abc", meta_size=2, runs=2)
        cls.table = json.loads(cls.out.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def test_export_sorted_by_quality(self):
        decks = self.table["decks"]
        self.assertEqual(len(decks), 16)
        q = [d["quality"] for d in decks]
        self.assertEqual(q, sorted(q, reverse=True))
        for d in decks:
            self.assertEqual(len(d["characters"]), 3)
            for c in d["characters"]:
                self.assertTrue(c["costume"] and c["main_weapon"] and len(c["parts"]) == 3 and c["companion"])
                self.assertTrue(all(p["id"] and p["main"] and len(p["subs"]) == 4 for p in c["parts"]))
            self.assertGreater(d["power"], 0)
        self.assertEqual(self.table["master_sha256"], "abc")

    def test_export_covers_low_to_high(self):
        q = [d["quality"] for d in self.table["decks"]]
        self.assertGreater(max(q) - min(q), 0.3)
        curve = self.table["power_to_quality"]
        self.assertGreaterEqual(len(curve), 2)
        self.assertEqual([p for p, _ in curve], sorted(p for p, _ in curve))
        self.assertEqual([x for _, x in curve], sorted(x for _, x in curve))

    def test_score_player_matches_sim(self):
        base = model.Save(model.rows_to_db(json.loads((FIX / "saves" / f"{SNAP}.json").read_text())), 1)
        score = ladder.score_player(base, tables(), self.experts, self.stage, meta_size=2, runs=2)
        self.assertEqual(score.power, 197235)
        meta = ladder.meta_decks(tables(), self.experts, self.stage, 2)
        deck = model.Deck(base, 2, 1)
        want = round(sum(w * sim.win_rate(deck, d, tables(), runs=2) for d, w in meta), 4)
        self.assertEqual(score.attack, want)

    def test_master_change_triggers_rewrite(self):
        self.assertFalse(ladder.needs_export(self.out, "abc"))
        self.assertTrue(ladder.needs_export(self.out, "other"))
        self.assertTrue(ladder.needs_export(Path(self.dir.name) / "missing.json", "abc"))

    def test_write_player_score(self):
        path = Path(self.dir.name) / "bunker_arena_players.json"
        ladder.write_player_score(path, 1, ladder.PlayerScore(0.4, 0.6, 200000))
        ladder.write_player_score(path, 2, ladder.PlayerScore(0.1, 0.2, 5000))
        data = json.loads(path.read_text())
        self.assertEqual(data["1"], {"attack": 0.4, "defense": 0.6, "power": 200000})
        self.assertEqual(data["2"]["power"], 5000)


if __name__ == "__main__":
    unittest.main()
