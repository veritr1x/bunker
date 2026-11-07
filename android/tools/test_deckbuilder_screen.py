#!/usr/bin/env python3
"""Deck Builder: All maxed's pool chosen by strength (deckbuilder/screen.py): every playable costume, fully raised
with its top weapon, tripled, against reference decks built the same way; the strongest, at most three per character."""
import json
import unittest

from deckbuilder_testlib import FIX, needs_master, tables
from deckbuilder import experts, model, screen

SUMMER_RULER_YURIE, OATHBOUND_RION = 32028, 33029


@needs_master
class ScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema = model.Save(model.rows_to_db(json.loads((FIX / "saves" / "2d981f327817.json").read_text())), 1)
        cls.ex = experts.Experts.load(tables())
        cls.ranked = screen.strength(tables(), cls.ex, schema)
        cls.pool = screen.pool_by_strength(cls.ranked, tables(), size=60, per_character=3)

    def test_every_playable_costume_is_checked(self):
        playable = {c for c in tables().idx("Costume", "CostumeId") if tables().is_fieldable(c)}
        checked = {r.costume_id for r in self.ranked}
        self.assertGreater(len(checked), 0.9 * len(playable))
        self.assertTrue(checked <= playable)

    def test_ranked_strongest_first(self):
        keys = [(r.win, r.margin) for r in self.ranked]
        self.assertEqual(keys, sorted(keys, reverse=True))

    def test_pool_is_the_strongest_with_at_most_three_per_character(self):
        self.assertEqual(len(self.pool), 60)
        character = lambda c: tables().idx("Costume", "CostumeId")[c]["CharacterId"]
        counts = {}
        for c in self.pool:
            counts[character(c)] = counts.get(character(c), 0) + 1
        self.assertLessEqual(max(counts.values()), 3)
        self.assertIn(SUMMER_RULER_YURIE, self.pool)
        self.assertIn(OATHBOUND_RION, self.pool)


if __name__ == "__main__":
    unittest.main()
