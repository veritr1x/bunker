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

    def test_page_shows_the_row_without_the_calendar(self):
        page = (root / "overlays/python/web/templates/patcher.html").read_text()
        before_calendar = page.split("{% if calendar %}", 1)[0]
        self.assertIn("{% if not calendar %}", before_calendar)  # with the calendar on, Next day takes its place
        self.assertIn('action="/patcher/new-day"', before_calendar)
        self.assertIn('t("pods.patcher.new_day")', before_calendar)  # "Start a new day"

    def test_calendar_row_has_next_day_before_jump_to(self):
        page = (root / "overlays/python/web/templates/patcher.html").read_text()
        calendar = page.split("{% if calendar %}", 1)[1]
        week, day, jump = (calendar.index(s) for s in ('t("pods.calendar.next_week")', 'action="/patcher/calendar/next-day"', 'action="/patcher/calendar/jump"'))
        self.assertLess(week, day)
        self.assertLess(day, jump)
        self.assertIn('t("pods.calendar.next_day")', calendar)

    def test_next_day_route_closes_the_game(self):
        self.assertIn("/patcher/calendar/next-day", android_runtime.CLOSES)


class NextDay(unittest.TestCase):
    """The calendar's Next day: the clock one whole day on, and a new day started (the daily reset)."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        for name, value in (("GAME_DB_PATH", Path(self.dir.name) / "game.db"),):
            patch = mock.patch.object(config, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.state = {"loop": 1, "loopStart": android_calendar.start_of_day(1_700_000_000_000), "jumpMillis": 0, "speed": 1}
        self.written = []
        for name, value in (("read_state", lambda: dict(self.state)), ("write_state", self.written.append),
                            ("now_ms", lambda: 1_700_000_000_000 + 3 * android_calendar.DAY)):
            patch = mock.patch.object(android_calendar, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_moves_the_calendar_one_day_and_starts_a_new_day(self):
        before = android_calendar.game_now(self.state, android_calendar.now_ms())
        response = android_calendar.calendar_next_day()
        self.assertEqual(len(self.written), 1)
        self.assertEqual(self.written[0]["jumpMillis"], android_calendar.DAY)
        self.assertEqual(android_calendar.game_now(self.written[0], android_calendar.now_ms()), before + android_calendar.DAY)
        saved = json.loads((Path(self.dir.name) / "day-start.json").read_text())
        self.assertEqual(saved, {"pressedRealMillis": android_calendar.now_ms()})
        self.assertTrue(android_calendar.client_days_file().exists())
        self.assertIn("message=", response.headers["location"])

    def test_without_the_calendar(self):
        with mock.patch.object(android_calendar, "read_state", lambda: None):
            response = android_calendar.calendar_next_day()
        self.assertIn("error=", response.headers["location"])
        self.assertFalse((Path(self.dir.name) / "day-start.json").exists())

    def test_at_the_loop_end_nothing_changes(self):
        with mock.patch.object(android_calendar, "jump", side_effect=ValueError("past the loop")):
            response = android_calendar.calendar_next_day()
        self.assertIn("error=", response.headers["location"])
        self.assertEqual(self.written, [])
        self.assertFalse((Path(self.dir.name) / "day-start.json").exists())


if __name__ == "__main__":
    unittest.main()
