#!/usr/bin/env python3
"""The Original calendar's "Show original dates" setting (android_calendar.py),
with the game data build stubbed. Needs the Android Python requirements."""
from pathlib import Path
import sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "android/app/src/main/python"))
import android_calendar as cal  # noqa: E402
from web import config  # noqa: E402

WEEK = cal.WEEK


class OriginalDates(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "release").mkdir()
        (self.dir / "saves").mkdir()
        (self.dir / "data").mkdir()
        self.patches = [mock.patch.object(config, "RELEASE_DIR", self.dir / "release"),
                        mock.patch.object(config, "GAME_DB_PATH", self.dir / "saves/game.db"),
                        mock.patch.object(config, "DATA_DIR", self.dir / "data"),
                        mock.patch.object(cal, "origin_file", lambda: self.dir / "origin.bin.e")]
        for p in self.patches:
            p.start()
        self.builds = []

        def build(origin, out, offset, view=False):
            self.builds.append(offset)
            Path(out).write_bytes(b"view")
        self.build = mock.patch.object(cal, "build_master", build)
        self.build.start()

    def tearDown(self):
        self.build.stop()
        for p in self.patches:
            p.stop()

    def state(self, **kw):
        return dict({"version": 1, "loop": 1, "loopStart": cal.LAUNCH + 100 * WEEK, "jumpMillis": 0, "speed": 1}, **kw)

    def test_setting_off_by_default(self):
        self.assertFalse(self.state().get("originalDates", False))

    def test_turning_on_builds_the_view_copy_once(self):
        state = self.state()
        cal.set_original_dates(state, True)
        cal.set_original_dates(state, True)
        self.assertTrue(state["originalDates"])
        self.assertEqual(self.builds, [0])
        self.assertTrue(cal.view_file().exists())
        self.assertEqual(cal.view_file().name, "calendar-view.bin.e")
        cal.set_original_dates(state, False)
        self.assertFalse(state["originalDates"])

    def test_view_copy_records_its_version(self):
        cal.set_original_dates(self.state(), True)
        self.assertEqual(cal.view_version_file().read_text(), cal.VIEW_VERSION)

    def test_outdated_view_copy_is_rebuilt_when_the_calendar_is_read(self):
        # A copy built before a fix to the copy (no version, or an older one) is rebuilt once.
        cal.view_file().write_bytes(b"old view")
        cal.write_state(self.state(originalDates=True))
        cal.read_state()
        self.assertEqual(self.builds, [0])
        self.assertEqual(cal.view_file().read_bytes(), b"view")
        cal.read_state()
        self.assertEqual(self.builds, [0])

    def test_no_view_copy_is_built_with_original_dates_off(self):
        cal.write_state(self.state())
        cal.read_state()
        self.assertEqual(self.builds, [])

    def test_turning_off_the_calendar_removes_the_view(self):
        cal.set_original_dates(self.state(), True)
        cal.turn_off()
        self.assertFalse(cal.view_file().exists())

    def test_today_shows_the_original_year(self):
        state = self.state(originalDates=True)
        now = cal.LAUNCH + 120 * WEEK
        with mock.patch.object(cal, "game_now", lambda s, real=None: now), mock.patch.object(cal, "entries", lambda: []):
            ctx = cal.context(state)
        self.assertTrue(ctx["originalDates"])
        self.assertEqual(ctx["today"], cal.day_label(now - 100 * WEEK))
        with mock.patch.object(cal, "game_now", lambda s, real=None: now), mock.patch.object(cal, "entries", lambda: []):
            self.assertEqual(cal.context(self.state())["today"], cal.day_label(now))


if __name__ == "__main__":
    unittest.main()
