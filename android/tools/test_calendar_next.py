#!/usr/bin/env python3
"""Where the Original calendar keeps the next loop's game data (android_calendar.py).
Needs the Android Python requirements (fastapi, msgpack)."""
from pathlib import Path
import json, sys, tempfile, unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "android/app/src/main/python"))
from web import config  # noqa: E402
import android_calendar as cal  # noqa: E402


class NextLoopData(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.saved = config.DATA_DIR, config.RELEASE_DIR, config.GAME_DB_PATH
        config.DATA_DIR = self.root / "tools"
        config.RELEASE_DIR = self.root / "assets/release"
        config.GAME_DB_PATH = self.root / "saves/game.db"
        for folder in (config.DATA_DIR, config.RELEASE_DIR, config.GAME_DB_PATH.parent):
            folder.mkdir(parents=True)

    def tearDown(self):
        config.DATA_DIR, config.RELEASE_DIR, config.GAME_DB_PATH = self.saved

    def test_it_sits_beside_the_master_data_under_the_name_the_server_looks_for(self):
        self.assertEqual(cal.next_file(), config.RELEASE_DIR / "calendar-next.bin")
        # The tools take the newest *.bin.e there as the master data.
        self.assertNotEqual(cal.next_file().suffix, ".e")

    def test_a_calendar_started_before_keeps_its_next_loop(self):
        old = config.DATA_DIR / "patcher/calendar-next.bin.e"
        old.parent.mkdir()
        old.write_bytes(b"loop2")
        # The full path of an app folder iOS has since moved.
        cal.write_state({"version": 1, "loop": 1, "loopStart": cal.LAUNCH, "next": "/old/container/calendar-next.bin.e", "nextLoop": 2})
        state = cal.read_state()
        self.assertEqual(cal.next_file().read_bytes(), b"loop2")
        self.assertFalse(old.exists())
        self.assertEqual(state["next"], "calendar-next.bin")
        self.assertEqual(json.loads(cal.state_path().read_text())["next"], "calendar-next.bin")

    def test_an_old_copy_goes_when_the_new_place_has_one(self):
        old = config.DATA_DIR / "patcher/calendar-next.bin.e"
        old.parent.mkdir()
        old.write_bytes(b"stale")
        cal.next_file().write_bytes(b"loop2")
        cal.write_state({"version": 1, "loop": 1, "loopStart": cal.LAUNCH, "next": "/old/container/calendar-next.bin.e", "nextLoop": 2})
        cal.read_state()
        self.assertEqual(cal.next_file().read_bytes(), b"loop2")
        self.assertFalse(old.exists())

    def test_turning_the_calendar_off_removes_it(self):
        cal.write_state({"version": 1, "loop": 1, "loopStart": cal.LAUNCH, "next": "calendar-next.bin", "nextLoop": 2})
        cal.next_file().write_bytes(b"loop2")
        cal.turn_off()
        self.assertFalse(cal.next_file().exists())


if __name__ == "__main__":
    unittest.main()
