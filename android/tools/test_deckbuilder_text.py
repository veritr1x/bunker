#!/usr/bin/env python3
"""Deck Builder's words (deckbuilder/text.py, explain.py, generate.py): made when shown, in the chosen language,
from whole catalogue sentences. Needs no master data."""
import unittest
from types import SimpleNamespace

import deckbuilder_testlib  # noqa: F401  (paths)
import bunker_text
from deckbuilder import explain, generate
from deckbuilder.text import Later

TABLES = SimpleNamespace(character_name=lambda c: {1: "Rion", 2: "Marie"}.get(c, "?"))


class Words(unittest.TestCase):
    def setUp(self):
        self.addCleanup(bunker_text.use, None)
        bunker_text.use(None)

    def test_a_later_is_made_when_shown(self):
        later = Later(lambda: bunker_text.t("pods.decks.strategy.stall"))
        self.assertEqual(str(later), "Stall")
        bunker_text.use({"pods.decks.strategy.stall": "Résister"})
        self.assertEqual(str(later), "Résister")

    def test_a_later_cannot_be_hashed(self):
        # Its text changes with the language, so a hash of it would too: a set or dict key would lose it.
        with self.assertRaises(TypeError):
            hash(Later(lambda: "x"))

    def test_an_element_mid_sentence_is_its_own_text(self):
        # Translators give the form a sentence needs (no lower-casing of the name a chip shows).
        reason = explain.short_reason("mono", ("fire",) * 3, [], None, TABLES)
        self.assertEqual(str(reason), "All fire: every fire damage boost on the team stacks.")
        bunker_text.use({"pods.decks.element_in_text.fire": "Feu", "common.element.fire": "FEU"})
        self.assertEqual(str(reason), "All Feu: every Feu damage boost on the team stacks.")

    def test_the_advantage_tag_uses_both_forms(self):
        tag = generate.advantage("fire", "wind")
        self.assertEqual(str(tag), "Fire vs wind ×1.2")
        bunker_text.use({"common.element.fire": "Feu", "pods.decks.element_in_text.wind": "Vent"})
        self.assertEqual(str(tag), "Feu vs Vent ×1.2")

    def test_an_element_the_catalogue_lacks_shows_its_own_name(self):
        # new game data: its name, never a key like "common.element.void"
        from deckbuilder import equip
        self.assertEqual(str(generate.advantage("void", "aether")), "void vs aether ×1.2")
        self.assertEqual(str(explain.short_reason("mono", ("void",) * 3, [], None, TABLES)),
                         "All void: every void damage boost on the team stacks.")
        self.assertEqual(equip.element_note("void"), "")          # no advantage known: no note
        self.assertEqual(equip._element("void"), "void")

    def test_no_pronoun_is_slotted_into_a_sentence(self):
        # Against General best there is no one to name: a sentence of its own, not "them" put into the other.
        self.assertNotIn("pods.decks.reason.them", bunker_text.english())
        reason = explain.short_reason("compromise_counter", ("dark",) * 3, [], None, TABLES)
        self.assertEqual(str(reason), "Land Compromise before their Dauntless or revive goes up, then finish them.")
        bunker_text.use({"pods.decks.reason.compromise_counter_any": "Compromise zuerst, dann sind sie dran."})
        self.assertEqual(str(reason), "Compromise zuerst, dann sind sie dran.")


class UnknownElement(unittest.TestCase):
    def test_an_element_the_catalogue_lacks_shows_its_name(self):
        # Elements come from the game data: one the catalogue doesn't know showed "common.element.ice".
        from deckbuilder import equip
        self.assertEqual(equip._element("ice"), "ice")
        self.assertEqual(str(generate.advantage("ice", "frost")), "ice vs frost ×1.2")
        self.assertEqual(equip._element("fire"), bunker_text.t("common.element.fire"))


if __name__ == "__main__":
    unittest.main()
