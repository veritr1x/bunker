#!/usr/bin/env python3
"""A language pack's master section in the game data (android_master_text): the English rows (LanguageType 2) of
the five text tables take the pack's words; Japanese and Korean rows and everything else stay. Uses the real master
data; skipped without it."""
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
sys.path.insert(0, str(root / "scripts"))
import android_calendar as cal  # noqa: E402
import android_challenges as ch  # noqa: E402
import android_master_text as mt  # noqa: E402

ORIGINAL = root / "inputs/20240404193219.bin.e"


class Texts(unittest.TestCase):
    def test_the_tables_are_the_exports(self):
        import master_text
        self.assertEqual(mt.TABLES, master_text.MASTER_TEXT_TABLES)

    def test_only_strings_of_the_five_tables(self):
        pack = {"master": {"m_dokan_text.100": "Hallo", "m_gift_text.1": 7, "m_quest.1": "x", "m_dokan_text": "y",
                           "m_dokan_text.abc": "z", "m_navi_cut_in_text.5": ""},
                "bunker": {"pods.gift.sender_in_game": "Von Bunker, mit Liebe."}}
        self.assertEqual(mt.texts(pack), {"m_dokan_text.100": "Hallo", "m_gift_text.90000": "Von Bunker, mit Liebe."})
        self.assertEqual(mt.texts({}), {})
        self.assertEqual(mt.texts({"master": ["m_dokan_text.100"], "bunker": "x"}), {})

    def test_the_bunker_gift_text_is_the_catalogues(self):
        # what the patcher adds in every language is the English the catalogue gives translators
        import json
        from patcher import patch_masterdata as pm
        english = json.loads((root / "translations/bunker/en.json").read_text())[mt.BUNKER_GIFT_KEY]
        self.assertEqual({row[2] for row in pm.TABLE_ROW_ADDITIONS["m_gift_text"]}, {english})
        self.assertEqual({row[0] for row in pm.TABLE_ROW_ADDITIONS["m_gift_text"]}, {int(mt.BUNKER_GIFT.rpartition(".")[2])})

    def test_hostile_keys_and_values_are_left_out(self):
        # isdigit() takes "²" and 5,000 digits, which int() refuses; a lone surrogate cannot be written to the data
        pack = {"master": {"m_dokan_text.²": "x", "m_dokan_text." + "9" * 5000: "x", "m_dokan_text.-5": "x",
                           "m_dokan_text.100": "a\ud800b", "m_dokan_text.101": "fine"}}
        self.assertEqual(mt.texts(pack), {"m_dokan_text.101": "fine"})

    def test_fingerprint(self):
        self.assertEqual(mt.fingerprint({}), "")
        self.assertEqual(mt.fingerprint({"a": "1", "b": "2"}), mt.fingerprint({"b": "2", "a": "1"}))
        self.assertNotEqual(mt.fingerprint({"a": "1"}), mt.fingerprint({"a": "2"}))


class Apply(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORIGINAL.is_file():
            raise unittest.SkipTest("needs inputs/20240404193219.bin.e")
        cls.toc, cls.blob = cal.read_master(ORIGINAL)

    def rows(self, table, changed=None):
        return ch.records(self.toc, self.blob, changed or {}, table)

    def test_english_rows_take_the_pack(self):
        changed = {}
        n = mt.apply(self.toc, self.blob, changed, {"m_dokan_text.100": "⟦Dimos⟧", "m_webview_panel_mission_complete_flavor_text.101": "⟦flavour⟧"})
        self.assertEqual(n, 2)
        dokan = {(r["DokanTextId"], r["LanguageType"]): r["Text"] for r in self.rows("m_dokan_text", changed)}
        before = {(r["DokanTextId"], r["LanguageType"]): r["Text"] for r in self.rows("m_dokan_text")}
        self.assertEqual(dokan[(100, 2)], "⟦Dimos⟧")
        self.assertEqual(dokan[(100, 1)], before[(100, 1)])  # Japanese stays
        self.assertEqual(dokan[(100, 3)], before[(100, 3)])  # Korean stays
        self.assertEqual({k: v for k, v in dokan.items() if k != (100, 2)}, {k: v for k, v in before.items() if k != (100, 2)})
        flavour = {r["WebviewPanelMissionCompleteFlavorTextId"]: r["CompleteFlavorText"]
                   for r in self.rows("m_webview_panel_mission_complete_flavor_text", changed) if r["LanguageType"] == 2}
        self.assertEqual(flavour[101], "⟦flavour⟧")

    def test_ids_the_data_lacks_change_nothing(self):
        changed = {}
        self.assertEqual(mt.apply(self.toc, self.blob, changed, {"m_dokan_text.99999999": "x"}), 0)
        self.assertEqual(mt.apply(self.toc, self.blob, changed, {}), 0)
        self.assertEqual(changed, {})

    def test_the_bunker_gift_text_follows_the_pack(self):
        # The patcher adds Bunker's gift row (90000) in every language; the pack's word goes to the English row.
        from patcher import patch_masterdata as pm
        changed = {}
        pm.apply_to_table(self.toc, self.blob, changed, "m_gift_text", lambda b: pm.add_table_rows(b, pm.TABLE_ROW_ADDITIONS["m_gift_text"]))
        self.assertEqual(mt.apply(self.toc, self.blob, changed, {"m_gift_text.90000": "Von Bunker, mit Liebe."}), 1)
        gift = {(r["GiftTextId"], r["LanguageType"]): r["Text"] for r in self.rows("m_gift_text", changed)}
        self.assertEqual(gift[(90000, 2)], "Von Bunker, mit Liebe.")
        self.assertEqual(gift[(90000, 1)], "From Bunker, with love.")


if __name__ == "__main__":
    unittest.main()
