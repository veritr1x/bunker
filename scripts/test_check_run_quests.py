#!/usr/bin/env python3
"""check_run_quests.py on the real game data: every earlier event run plays its own quest copies, with their
scenes, its unlocks and drops, and medals its exchange takes. Needs the original master data
(inputs/20240404193219.bin.e, or BUNKER_TEST_MASTER); skipped without it."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MASTER = Path(os.environ.get("BUNKER_TEST_MASTER", ROOT / "inputs/20240404193219.bin.e"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))


@unittest.skipUnless(MASTER.is_file(), "needs the original master data")
class RealRuns(unittest.TestCase):
    def test_every_earlier_run_is_mapped_and_linked(self):
        import tempfile
        import android_calendar as cal
        import check_run_quests as check
        from tools import dump_masterdata
        schemas = dump_masterdata.load_schemas()
        with tempfile.TemporaryDirectory() as temp:
            built = Path(temp) / "calendar.bin.e"
            cal.build_master(MASTER, built, 0)
            toc, blob = cal.read_master(built)
        names = check.TABLES + cal.COPY_SCENE_TABLES
        rows = {n: cal.table_rows(toc, blob, {}, schemas, n) for n in names if n in toc}
        problems, summary = check.check(rows, cal.event_run_data(), cal)
        self.assertEqual(problems, [])
        self.assertEqual(summary["earlier runs"], 33)
        self.assertGreater(summary["quest copies"], 1000)


if __name__ == "__main__":
    unittest.main()
