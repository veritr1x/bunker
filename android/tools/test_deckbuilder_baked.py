#!/usr/bin/env python3
"""Deck Builder: All maxed results baked at build time (deckbuilder/baked.py): the shipped format, its ranked
lists, the fighter fingerprint."""
import json
import tempfile
import unittest
from pathlib import Path

import deckbuilder_testlib  # noqa: F401  (paths)
from deckbuilder import baked


def rec(l, aw, am, dw, dm, f):
    return baked.Record(tuple(l), aw, am, dw, dm, f)


ROWS = [rec((1, 2, 3), 1.0, 0.25, 0.8, 0.1, 400000), rec((1, 2, 4), 0.6, -0.1, 1.0, 0.5, 350000),
        rec((2, 3, 4), 0.6, 0.2, 0.0, -0.4, 500000), rec((4, 3, 1), 0.0, -0.9, 0.4, 0.05, 300000)]
LOADOUTS = {c: {"costume_id": c, "element": e, "role": "attacker", "main_weapon": 100 + c, "subs": [], "companion": None,
                "memoir_set": None, "debris": None} for c, e in ((1, "fire"), (2, "water"), (3, "wind"), (4, "dark"))}


class FormatTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name)
        baked.write(self.path, LOADOUTS, "abc123", ROWS, extra={"bake": "test"})
        self.b = baked.Baked.load(self.path)

    def tearDown(self):
        self.dir.cleanup()

    def test_round_trip_in_rank_order(self):
        """Attack ranks by attack win then margin (and Force), defense by defense win then margin; values kept to
        4 decimals, lineups in slot order."""
        self.assertEqual([r.lineup for r in self.b.records("attack")], [(1, 2, 3), (2, 3, 4), (1, 2, 4), (4, 3, 1)])
        self.assertEqual([r.lineup for r in self.b.records("defense")], [(1, 2, 4), (1, 2, 3), (4, 3, 1), (2, 3, 4)])
        self.assertEqual(self.b.records("attack")[0], ROWS[0])
        self.assertEqual(self.b.fingerprint, "abc123")
        self.assertEqual(self.b.element(2), "water")
        self.assertEqual(self.b.meta["bake"], "test")

    def test_keeps_only_the_top(self):
        b = baked.write(self.path, LOADOUTS, "x", ROWS, keep=2)
        b = baked.Baked.load(self.path)
        self.assertEqual([r.lineup for r in b.records("attack")], [(1, 2, 3), (2, 3, 4)])
        self.assertEqual([r.lineup for r in b.records("defense")], [(1, 2, 4), (1, 2, 3)])

    def test_missing_data_is_none(self):
        self.assertIsNone(baked.Baked.load(self.path / "nowhere"))


class DebrisTest(unittest.TestCase):
    """The game holds one of each debris: in a deck, a debris an earlier character already has is replaced on the
    later one by its next in order (first not taken)."""
    def test_a_debris_twice_goes_to_the_next(self):
        lo = {c: dict(LOADOUTS[c], debris=d) for c, d in ((1, 900), (2, 900), (3, 901))}
        order = lambda element: [900, 901, 902]
        out = baked.deck_loadouts((1, 2, 3), lo, order)
        self.assertEqual([x["debris"] for x in out], [900, 902, 901])
        self.assertEqual([x["costume_id"] for x in out], [1, 2, 3])
        self.assertEqual(lo[2]["debris"], 900)                  # the shared loadouts are not changed

    def test_no_debris_or_none_left(self):
        lo = {c: dict(LOADOUTS[c], debris=d) for c, d in ((1, 900), (2, 900), (3, None))}
        out = baked.deck_loadouts((1, 2, 3), lo, lambda e: [900])
        self.assertEqual([x["debris"] for x in out], [900, None, None])


if __name__ == "__main__":
    unittest.main()
