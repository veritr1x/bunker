import os
import unittest
from pathlib import Path

from master_text import MASTER_TEXT_TABLES, load_master_tables, texts_from_tables

ROOT = Path(__file__).resolve().parents[1]
MASTER = Path(os.environ.get("BUNKER_MASTER", ROOT / "inputs/20240404193219.bin.e"))


class TextsFromTablesTest(unittest.TestCase):
    def test_texts_by_language(self):
        tables = {"m_gift_text": [
            {"GiftTextId": 1, "LanguageType": 2, "Text": "Earned"},
            {"GiftTextId": 1, "LanguageType": 1, "Text": "獲得"},
            {"GiftTextId": 1, "LanguageType": 3, "Text": "획득"},
            {"GiftTextId": 2, "LanguageType": 9, "Text": "x"},
        ]}
        out = texts_from_tables(tables)
        self.assertEqual(out["en"], {"m_gift_text.1": "Earned"})
        self.assertEqual(out["ja"], {"m_gift_text.1": "獲得"})
        self.assertEqual(out["ko"], {"m_gift_text.1": "획득"})

    def test_other_text_column(self):
        rows = {"m_webview_panel_mission_complete_flavor_text": [
            {"WebviewPanelMissionCompleteFlavorTextId": 7, "LanguageType": 2, "CompleteFlavorText": "Done"},
        ]}
        self.assertEqual(texts_from_tables(rows)["en"],
                         {"m_webview_panel_mission_complete_flavor_text.7": "Done"})

    def test_missing_tables_are_fine(self):
        self.assertEqual(texts_from_tables({}), {"en": {}, "ja": {}, "ko": {}})


@unittest.skipUnless(MASTER.is_file(), "Requires the master data (set BUNKER_MASTER to the .bin.e file).")
class RealMasterTest(unittest.TestCase):
    def test_every_table_has_english(self):
        en = texts_from_tables(load_master_tables(MASTER, MASTER_TEXT_TABLES))["en"]
        for table in MASTER_TEXT_TABLES:
            self.assertTrue(any(key.startswith(table + ".") for key in en), table)


if __name__ == "__main__":
    unittest.main()
