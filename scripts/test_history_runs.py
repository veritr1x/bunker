#!/usr/bin/env python3
"""Which runs calendar_history.py keeps (scripts/calendar_history.py)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calendar_history as ch  # noqa: E402

DAY = 24 * 60 * 60 * 1000
T0 = ch.LAUNCH


class Runs(unittest.TestCase):
    def test_a_run_seen_live_during_it_counts(self):
        run = (T0, T0 + 20 * DAY)
        self.assertTrue(ch.was_live(run, {T0 + 7 * DAY}, [T0 + 7 * DAY]))

    def test_a_run_whose_end_moved_later_counts(self):
        # Chapter 1 ran 2 to 22 December 2021; the files of those weeks gave it an end in 2099.
        run = (T0, T0 + 20 * DAY)
        self.assertTrue(ch.was_live(run, {T0 + 7 * DAY, T0 + 90 * DAY}, [T0 + 7 * DAY, T0 + 14 * DAY]))

    def test_a_run_never_live_while_dated_is_a_placeholder(self):
        # Item 29: every file published during its dates had it missing.
        run = (T0, T0 + 20 * DAY)
        self.assertFalse(ch.was_live(run, {T0 + 90 * DAY}, [T0 + 7 * DAY, T0 + 14 * DAY]))

    def test_a_run_between_two_files_is_kept(self):
        # A one-day schedule no weekly file falls in cannot be checked.
        run = (T0 + 2 * DAY, T0 + 3 * DAY)
        self.assertTrue(ch.was_live(run, set(), [T0, T0 + 7 * DAY]))

    def test_the_file_time_comes_from_its_name(self):
        self.assertEqual(ch.file_time(Path("20210801231936.bin.e")), 1627859976000)
        self.assertIsNone(ch.file_time(Path("master.bin.e")))


class NoticeCorrections(unittest.TestCase):
    def test_a_notice_moves_a_runs_end(self):
        # Record: Seat of Shadow (Resurrected) ends Dec. 2 17:59 PST (notices 1442, 1445);
        # the last weekly master moved it a day later without a notice.
        tables = {"m_event_quest_chapter": {"rows": {"507": [[1, 2], [1700186400000, 1701655199000]]}}}
        ch.apply_corrections(tables)
        self.assertEqual(tables["m_event_quest_chapter"]["rows"]["507"][1], [1700186400000, 1701568799000])

    def test_the_committed_history_has_the_corrections(self):
        import json
        rows = json.loads((ch.PYTHON / "calendar_history.json").read_text())["tables"]["m_event_quest_chapter"]["rows"]
        self.assertIn([1700186400000, 1701568799000], rows["507"])



class WrittenRuns(unittest.TestCase):
    def test_the_first_daily_set_runs_from_launch(self):
        # The masters date daily missions 21-26 2000-01-02 to 9999 at launch, a
        # placeholder to live(); they ran until 31-36 opened on 24 November 2021.
        tables = {"m_mission_term": {"rows": {"1002": [[1632470400000, 4086576000000]]}}}
        ch.apply_corrections(tables)
        self.assertEqual(tables["m_mission_term"]["rows"]["1002"], [[ch.LAUNCH, 1637740799000]])

    def test_the_committed_history_has_the_written_runs(self):
        import json
        tables = json.loads((ch.PYTHON / "calendar_history.json").read_text())["tables"]
        for (table, key), runs in ch.RUNS.items():
            self.assertEqual(tables[table]["rows"][key], runs)

class LaunchRuns(unittest.TestCase):
    def test_the_daily_quests_run_from_launch(self):
        # The masters date daily chapters 1-6 and 8 from 2020-05-06 at launch, a
        # placeholder to live(); they were open until the first campaign (13 October 2021).
        tables = {"m_event_quest_chapter": {"rows": {"1": [[1635148800000, 1637546399000], [1644825600000, 253390406340000]]}}}
        ch.apply_corrections(tables)
        self.assertEqual(tables["m_event_quest_chapter"]["rows"]["1"],
                         [[ch.LAUNCH, 1634090399000], [1635148800000, 1637546399000], [1644825600000, 253390406340000]])

    def test_a_launch_run_is_added_once(self):
        tables = {"m_quest_schedule": {"rows": {"2": [[1635148800000, 1637546399000]]}}}
        ch.apply_corrections(ch.apply_corrections(tables))
        self.assertEqual(tables["m_quest_schedule"]["rows"]["2"], [[ch.LAUNCH, 1634090399000], [1635148800000, 1637546399000]])

    def test_the_committed_history_has_the_launch_runs(self):
        import json
        tables = json.loads((ch.PYTHON / "calendar_history.json").read_text())["tables"]
        self.assertEqual(len(ch.LAUNCH_RUNS), 14)
        for (table, key), end in ch.LAUNCH_RUNS.items():
            self.assertEqual(tables[table]["rows"][key][0], [ch.LAUNCH, end], (table, key))


if __name__ == "__main__":
    unittest.main()
