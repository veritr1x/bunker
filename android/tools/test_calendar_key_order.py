#!/usr/bin/env python3
"""The Original calendar's game data keeps every table in its key order. The game finds rows by binary search
(MasterMemory): the restored runs' chapter copies (ids + COPY_STEP), written beside the rows they copy, left the
event chapter table and those keyed by it out of order, and CalculatorQuest.TryGetEventQuestType no longer found
chapters, so every auto-repeat stopped after one clear with "The quest period has ended"."""
from pathlib import Path
import sys, tempfile, unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "android/app/src/main/python"))
import android_calendar as cal  # noqa: E402
from test_calendar_history import cells, row, table  # noqa: E402


class KeyOrder(unittest.TestCase):
    def test_rows_go_back_in_key_order(self):
        blob = cal.keep_key_order(table(row(510, 1), row(510 + cal.COPY_STEP, 2), row(511, 3), row(511, 4)))
        self.assertEqual(cells(blob), [[510, 1], [511, 3], [511, 4], [510 + cal.COPY_STEP, 2]])   # ties keep their order

    def test_a_calendar_in_use_is_rebuilt(self):
        """Calendars built before the fix are rebuilt on update (read_state compares the data version), and so is
        the "Show original dates" copy."""
        self.assertEqual((cal.DATA_VERSION, cal.VIEW_VERSION), (2, "3"))

    def test_a_built_calendar_keeps_every_sorted_table_sorted(self):
        from deckbuilder_testlib import MASTER_BIN
        from tools import dump_masterdata
        if not Path(MASTER_BIN).exists():
            self.skipTest("no master data")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "calendar.bin.e"
            cal.build_master(MASTER_BIN, out, 0)
            schemas = dump_masterdata.load_schemas()
            otoc, oblob = cal.read_master(MASTER_BIN)
            ctoc, cblob = cal.read_master(out)
            firsts = lambda toc, blob, t: [r[0] for r in cal._read(toc, blob, {}, schemas, t, schemas[t][1][0][2])]
            in_order = lambda ids: all(a <= b for a, b in zip(ids, ids[1:]))
            for t in ("m_event_quest_chapter", "m_event_quest_sequence", "m_event_quest_sequence_group",
                      "m_event_quest_tower_accumulation_reward", "m_event_quest_tower_asset", "m_webview_mission", "m_webview_panel_mission"):
                with self.subTest(table=t):
                    self.assertTrue(in_order(firsts(otoc, oblob, t)))
                    ids = firsts(ctoc, cblob, t)
                    self.assertGreater(len(ids), len(firsts(otoc, oblob, t)) - 1)
                    self.assertTrue(in_order(ids), t)


if __name__ == "__main__":
    unittest.main()
