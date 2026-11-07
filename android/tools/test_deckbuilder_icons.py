#!/usr/bin/env python3
"""Deck Builder: each piece's icon in the game's files (the _standard art the game's notices
use), and a memoir set's name."""
import unittest

from deckbuilder_testlib import needs_master, tables


@needs_master
class IconTest(unittest.TestCase):
    def test_icon_paths(self):
        t = tables()
        self.assertEqual(t.icon_asset("weapon", 100001), "ui/weapon/wp001060/wp001060_standard.assetbundle")
        self.assertEqual(t.icon_asset("companion", 1), "ui/companion/cm001001/cm001001_standard.assetbundle")
        self.assertEqual(t.icon_asset("memoir", 1), "ui/memory/memory001/memory001_standard.assetbundle")
        self.assertEqual(t.icon_asset("debris", 10100834), "ui/thought/thought100008/thought100008_standard.assetbundle")

    def test_unknown_pieces_have_no_icon(self):
        t = tables()
        self.assertIsNone(t.icon_asset("weapon", 1))
        self.assertIsNone(t.icon_asset("costume", 100001))

    def test_memoir_set_name(self):
        self.assertEqual(tables().memoir_set_name(1), "Solemnity")


if __name__ == "__main__":
    unittest.main()
