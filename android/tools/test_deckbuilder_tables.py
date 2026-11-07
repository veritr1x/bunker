#!/usr/bin/env python3
"""Deck Builder: which costumes are the player's kind (deckbuilder/tables.py)."""
import unittest

from deckbuilder_testlib import needs_master, tables


@needs_master
class FieldableTest(unittest.TestCase):
    def test_the_280_playable_costumes_and_no_enemies(self):
        """The game's playable costumes (5-digit ids, 33 characters); enemy and boss costumes (character 10001,
        1000001: ids like 118110201) are not, whether or not a name was found for them."""
        t = tables()
        field = [c for c in t.idx("Costume", "CostumeId") if t.is_fieldable(c)]
        self.assertEqual(len(field), 280)
        self.assertTrue(all(len(str(c)) == 5 for c in field))
        self.assertEqual(len({t.idx("Costume", "CostumeId")[c]["CharacterId"] for c in field}), 33)
        for enemy in (118110201, 113600023, 1000022, 103270548):
            self.assertFalse(t.is_playable(enemy), enemy)


if __name__ == "__main__":
    unittest.main()
