import os
import tempfile
import unittest
from pathlib import Path

import master_text
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

    def test_context_languages_keep_only_english_keys(self):
        tables = {"m_dokan_text": [
            {"DokanTextId": 1, "LanguageType": 2, "Text": "Hi"},
            {"DokanTextId": 1, "LanguageType": 1, "Text": "やあ"},
            {"DokanTextId": 5, "LanguageType": 1, "Text": "日本だけ"},
            {"DokanTextId": 6, "LanguageType": 3, "Text": "한국만"},
        ]}
        out = texts_from_tables(tables)
        self.assertEqual(out["ja"], {"m_dokan_text.1": "やあ"})
        self.assertEqual(out["ko"], {})

    def test_missing_tables_are_fine(self):
        self.assertEqual(texts_from_tables({}), {"en": {}, "ja": {}, "ko": {}})


def encrypted_master(path: Path, toc: dict) -> Path:
    """A master data file (.bin.e) holding only a table of contents."""
    import dump_masterdata
    import msgpack
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    key, iv = bytes.fromhex(dump_masterdata.DEFAULT_KEY), bytes.fromhex(dump_masterdata.DEFAULT_IV)
    path.write_bytes(AES.new(key, AES.MODE_CBC, iv).encrypt(pad(msgpack.packb(toc), AES.block_size)))
    return path


class LoadTablesTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_missing_table_is_an_error(self):
        master = encrypted_master(self.dir / "m.bin.e", {})
        with self.assertRaises(ValueError) as caught:
            load_master_tables(master, ["m_gift_text"])
        self.assertIn("m_gift_text", str(caught.exception))

    def test_archive_shares_the_loader(self):
        # Pod Programs' Archive reads the same file; one loader serves both. It tolerates missing tables.
        import archive.index
        master = encrypted_master(self.dir / "m.bin.e", {})
        self.assertEqual(archive.index.load_tables(master, ["m_gift_text"]), {})
        self.assertIs(master_text.load_tables, archive.index.load_tables)


@unittest.skipUnless(MASTER.is_file(), "Requires the master data (set BUNKER_MASTER to the .bin.e file).")
class RealMasterTest(unittest.TestCase):
    def test_every_table_has_english(self):
        en = texts_from_tables(load_master_tables(MASTER, MASTER_TEXT_TABLES))["en"]
        for table in MASTER_TEXT_TABLES:
            self.assertTrue(any(key.startswith(table + ".") for key in en), table)


if __name__ == "__main__":
    unittest.main()
