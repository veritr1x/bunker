#!/usr/bin/env python3
"""Pod Programs › Gift: the game data carries the gift text "From Bunker, with
love." (m_gift_text 90000), from the master-data patcher that the content
presets and the Original calendar both use. Needs the Android Python
requirements and prepared sources (scripts/prepare.py)."""
from pathlib import Path
import sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
from patcher import patch_masterdata as pm  # noqa: E402

ORIGINAL = root / "inputs/20240404193219.bin.e"
TEXT = "From Bunker, with love."
ROWS = [[90000, 1, TEXT], [90000, 2, TEXT], [90000, 3, TEXT]]


class GiftText(unittest.TestCase):
    def test_the_patcher_adds_the_gift_text(self):
        self.assertEqual(pm.TABLE_ROW_ADDITIONS["m_gift_text"], ROWS)
        # Above the game's own ids (its highest is 9004), so the table stays sorted.
        self.assertTrue(all(row[0] > 9004 for row in ROWS))

    def test_presets_and_calendar_carry_it(self):
        if not ORIGINAL.is_file():
            self.skipTest("needs inputs/20240404193219.bin.e")
        import android_calendar as cal
        from tools import dump_masterdata
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "out.bin.e"
            cal.build_master(ORIGINAL, out, 0)
            toc, blob = cal.read_master(out)
        offset, length = toc["m_gift_text"]
        columns = dump_masterdata.load_schemas()["m_gift_text"][1]
        rows = dump_masterdata.rows_to_dicts(dump_masterdata.decompress_table(blob, offset, length), columns)
        keys = [(r["GiftTextId"], r["LanguageType"]) for r in rows]
        self.assertEqual(keys, sorted(keys))
        ours = [[r["GiftTextId"], r["LanguageType"], r["Text"]] for r in rows if r["GiftTextId"] == 90000]
        self.assertEqual(ours, ROWS)

    def test_gift_text_is_added_to_any_game_data(self):
        # Game data made before this build, imported or restored: Gift adds the
        # text itself (android_gift.add_gift_text), changing nothing else.
        if not ORIGINAL.is_file():
            self.skipTest("needs inputs/20240404193219.bin.e")
        import android_calendar as cal
        import android_gift
        from tools import dump_masterdata

        def gift_rows(path):
            toc, blob = cal.read_master(path)
            offset, length = toc["m_gift_text"]
            rows = dump_masterdata.rows_to_dicts(dump_masterdata.decompress_table(blob, offset, length),
                                                 dump_masterdata.load_schemas()["m_gift_text"][1])
            return toc, blob, [[r["GiftTextId"], r["LanguageType"], r["Text"]] for r in rows]
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "out.bin.e"
            self.assertTrue(android_gift.add_gift_text(ORIGINAL, out))
            before_toc, before_blob, before = gift_rows(ORIGINAL)
            after_toc, after_blob, after = gift_rows(out)
            self.assertEqual(after, before + ROWS)
            for table, (start, length) in before_toc.items():  # every other table byte for byte
                if table != "m_gift_text":
                    s2, l2 = after_toc[table]
                    self.assertEqual(after_blob[s2:s2 + l2], before_blob[start:start + length], table)
            again = Path(work) / "again.bin.e"
            self.assertFalse(android_gift.add_gift_text(out, again))  # already there: nothing to do


if __name__ == "__main__":
    unittest.main()
