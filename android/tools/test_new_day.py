#!/usr/bin/env python3
"""Pod Programs › Content › Start a new day: day-start.json for the server
(gametime.StartOfDay), the client-days reset, and the game closed so it starts
the new day fresh. Needs fastapi and jinja2."""
from pathlib import Path
import json, sys, tempfile, unittest
from unittest import mock

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
import android_calendar  # noqa: E402
import android_patcher  # noqa: E402
import android_runtime  # noqa: E402
from web import config  # noqa: E402


class NewDay(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patch = mock.patch.object(config, "GAME_DB_PATH", Path(self.dir.name) / "game.db")
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.dir.cleanup)

    def test_press_writes_the_file(self):
        android_patcher.start_new_day(1_700_000_000_123)
        saved = json.loads((Path(self.dir.name) / "day-start.json").read_text())
        self.assertEqual(saved, {"pressedRealMillis": 1_700_000_000_123})

    def test_press_marks_the_client_days_reset(self):
        android_patcher.start_new_day(1_700_000_000_000)
        self.assertTrue(android_calendar.client_days_file().exists())

    def test_new_day_today(self):
        android_patcher.start_new_day(1_700_000_000_000)
        self.assertTrue(android_patcher.new_day_today(1_700_000_000_000 + 60_000))
        self.assertFalse(android_patcher.new_day_today(1_700_000_000_000 + 2 * 86_400_000))

    def test_new_day_today_reads_the_calendar_clock_without_its_upkeep(self):
        # GET /mods asks this: it follows a moved calendar clock, but must not
        # rebuild calendar files as read_state does.
        hour = 3_600_000
        day = android_calendar.start_of_day(1_700_000_000_000 + 30 * 86_400_000)  # a game day's start
        jump = 12 * hour
        state = Path(self.dir.name) / "calendar.json"
        state.write_text(json.dumps({"loopStart": 1, "jumpMillis": jump}))
        pressed = day + hour - jump  # real time; on the game clock, 01:00 that day
        android_patcher.start_new_day(pressed)
        with mock.patch.object(android_calendar, "state_path", lambda: state), \
                mock.patch.object(android_calendar, "read_state", side_effect=AssertionError("calendar upkeep")):
            self.assertTrue(android_patcher.new_day_today(pressed + 13 * hour))

    def test_route_closes_the_game(self):
        # The game keeps day markers in memory that only a fresh start clears.
        self.assertIn("/patcher/new-day", android_runtime.CLOSES)

    def test_page_shows_the_row(self):
        page = (root / "overlays/python/web/templates/patcher.html").read_text()
        before_calendar = page.split("{% if calendar %}", 1)[0]
        self.assertIn('action="/patcher/new-day"', before_calendar)  # shown with the calendar on and off
        self.assertIn("Start a new day", before_calendar)


if __name__ == "__main__":
    unittest.main()
