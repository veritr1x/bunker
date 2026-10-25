#!/usr/bin/env python3
"""The Original calendar's restored runs (android_calendar.py, calendar_history.json)
on small made-up tables. Needs the Android Python requirements (fastapi, msgpack)."""
from pathlib import Path
import json, struct, sys, unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "android/app/src/main/python"))
import msgpack  # noqa: E402
import android_calendar as cal  # noqa: E402

DAY = 24 * 60 * 60 * 1000
T0 = 1627437600000  # global launch


def row(*cells):
    """A row as the game data stores it: dates as whole int64 cells."""
    parts = [b"\xd3" + struct.pack(">q", c) if isinstance(c, Date) else msgpack.packb(c) for c in cells]
    return bytes([0x90 | len(parts)]) + b"".join(parts)


class Date(int):
    pass


def table(*rows):
    return bytes([0x90 | len(rows)]) + b"".join(rows)


def cells(blob):
    return [[msgpack.unpackb(c) for c in values] for _, values in cal._rows(blob)]


class RestoredRuns(unittest.TestCase):
    def test_a_finished_run_comes_back_as_the_first(self):
        self.assertEqual(cal.runs((T0 + 900 * DAY, T0 + 910 * DAY), [[T0, T0 + 40 * DAY], [T0 + 900 * DAY, T0 + 910 * DAY]]),
                         [(T0, T0 + 40 * DAY), (T0 + 900 * DAY, T0 + 910 * DAY)])

    def test_content_open_for_good_opens_from_its_first_run(self):
        never = cal.NEVER
        self.assertEqual(cal.runs((T0 + 200 * DAY, never), [[T0 + 90 * DAY, T0 + 110 * DAY], [T0 + 200 * DAY, never]]),
                         [(T0 + 90 * DAY, never)])

    def test_a_row_without_history_keeps_its_dates(self):
        self.assertEqual(cal.runs((T0, T0 + DAY), []), [(T0, T0 + DAY)])

    def test_a_chapter_gets_a_copy_for_each_later_run(self):
        spec = {"key": [0], "dates": [1, 2], "rows": {"510": [[T0, T0 + 40 * DAY], [T0 + 600 * DAY, T0 + 620 * DAY]]}}
        copies = {}
        blob = cal.restore_runs(table(row(510, Date(T0 + 600 * DAY), Date(T0 + 620 * DAY), 7), row(511, Date(T0), Date(T0 + DAY), 8)), spec, copies)
        self.assertEqual(cells(blob), [[510, T0, T0 + 40 * DAY, 7], [510 + cal.COPY_STEP, T0 + 600 * DAY, T0 + 620 * DAY, 7], [511, T0, T0 + DAY, 8]])
        self.assertEqual(copies, {510: [510 + cal.COPY_STEP]})
        # Dates stay whole int64 cells, which the loop's shift moves.
        self.assertEqual(cal.shift_table(bytearray(blob), {1, 2}, 7 * DAY), 6)

    def test_other_tables_take_the_first_run_only(self):
        spec = {"key": [0], "dates": [1, 2], "rows": {"38": [[T0 + 35 * DAY, T0 + 45 * DAY], [T0 + 98 * DAY, T0 + 108 * DAY]]}}
        blob = cal.restore_runs(table(row(38, Date(T0 + 98 * DAY), Date(T0 + 108 * DAY))), spec)
        self.assertEqual(cells(blob), [[38, T0 + 35 * DAY, T0 + 45 * DAY]])

    def test_rows_keyed_by_a_copied_chapter_are_copied(self):
        blob = cal.copy_chapter_rows(table(row(302, 1009), row(303, 1010)), {302: [302 + cal.COPY_STEP]})
        self.assertEqual(cells(blob), [[302, 1009], [302 + cal.COPY_STEP, 1009], [303, 1010]])

    def test_history_names_only_start_and_end_columns(self):
        for name, spec in json.loads(cal.HISTORY.read_text())["tables"].items():
            self.assertEqual(len(spec["dates"]), 2, name)
            self.assertTrue(spec["rows"], name)


if __name__ == "__main__":
    unittest.main()
