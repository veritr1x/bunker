#!/usr/bin/env python3
"""The Original calendar's "Show original dates" setting (android_calendar.py),
with the game data build stubbed. Needs the Android Python requirements."""
from pathlib import Path
import sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "android/app/src/main/python"))
import android_calendar as cal  # noqa: E402
import android_patcher as ap  # noqa: E402
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
        self.builds, self.chapters = [], []
        self.reached = {101}
        self.patches.append(mock.patch.object(cal, "reached_chapters", lambda: set(self.reached)))
        self.patches.append(mock.patch.object(cal, "all_chapters", lambda: {101, 102, 103}))
        self.patches[-1].start(); self.patches[-2].start()

        def build(origin, out, offset, view=False, open_chapters=None):
            self.builds.append(offset)
            self.chapters.append(open_chapters)
            Path(out).write_bytes(b"view")
        self.build = mock.patch.object(cal, "build_master", build)
        self.build.start()

    def tearDown(self):
        self.build.stop()
        for p in self.patches:
            p.stop()

    def state(self, **kw):
        return dict({"version": 1, "loop": 1, "loopStart": cal.LAUNCH + 100 * WEEK, "jumpMillis": 0, "speed": 1,
                     "dataVersion": cal.DATA_VERSION}, **kw)

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
        self.assertEqual(cal.view_version_file().read_text(), cal.VIEW_VERSION + ":1")

    def test_outdated_view_copy_is_rebuilt_when_the_calendar_is_read(self):
        # A copy built before a fix to the copy (no version, or an older one) is rebuilt once.
        cal.view_file().write_bytes(b"old view")
        cal.write_state(self.state(originalDates=True))
        cal.read_state()
        self.assertEqual(self.builds, [0])
        self.assertEqual(cal.view_file().read_bytes(), b"view")
        cal.read_state()
        self.assertEqual(self.builds, [0])

    def test_an_update_rebuilds_the_view_copy_without_pod_programs(self):
        # 1.6.1 built the copy; the launcher runs this before the server starts.
        cal.view_file().write_bytes(b"old view")
        cal.write_state(self.state(originalDates=True))
        self.assertTrue(ap.update_for("1.6.2"))
        self.assertEqual(self.builds, [0])
        self.assertEqual(cal.view_file().read_bytes(), b"view")
        self.assertEqual(ap.updated_file().read_text(), "1.6.2")

    def test_an_update_runs_once_per_version(self):
        cal.write_state(self.state(originalDates=True))
        ap.update_for("1.6.2")
        self.assertFalse(ap.update_for("1.6.2"))
        self.assertTrue(ap.update_for("1.6.3"))
        self.assertEqual(ap.updated_file().read_text(), "1.6.3")

    def test_an_update_rebuilds_game_data_from_before(self):
        cal.write_state({k: v for k, v in self.state().items() if k != "dataVersion"})
        with mock.patch.object(cal.patcher, "activate"):
            ap.update_for("1.6.2")
        self.assertEqual(self.builds, [100 * WEEK])

    def test_no_view_copy_is_built_with_original_dates_off(self):
        cal.write_state(self.state())
        cal.read_state()
        self.assertEqual(self.builds, [])

    def test_loop_one_opens_only_reached_chapters(self):
        with mock.patch.object(cal.patcher, "activate", lambda candidate, label: None):
            cal.activate_loop(self.state())
            cal.activate_loop(self.state(loop=2))
        self.assertEqual(self.chapters, [{101}, {101, 102, 103}])

    def test_view_opens_reached_chapters_in_loop_one_and_all_later(self):
        cal.set_original_dates(self.state(), True)
        cal.view_file().unlink()
        cal.set_original_dates(self.state(loop=2), True)
        self.assertEqual(self.chapters, [{101}, {101, 102, 103}])

    def test_view_built_for_loop_one_is_rebuilt_in_loop_two(self):
        cal.set_original_dates(self.state(), True)
        cal.write_state(self.state(loop=2, originalDates=True, dataVersion=cal.DATA_VERSION))
        cal.read_state()
        self.assertEqual(len(self.builds), 2)

    def test_game_data_from_before_is_rebuilt_once(self):
        activated = []
        with mock.patch.object(cal.patcher, "activate", lambda candidate, label: activated.append(label)), \
             mock.patch.object(cal, "prepare_next", lambda state: None):
            old = self.state()
            del old["dataVersion"]  # a calendar from before
            cal.write_state(old)
            cal.read_state()
            cal.read_state()
        self.assertEqual(len(activated), 1)
        self.assertEqual(cal.read_state.__module__, "android_calendar")
        self.assertEqual(cal.runtime.read_json(cal.state_path())["dataVersion"], cal.DATA_VERSION)

    def test_reached_chapters_from_the_save(self):
        import sqlite3
        db = sqlite3.connect(config.GAME_DB_PATH)
        db.execute("create table user_quests (user_id, quest_id, quest_state_type, clear_count)")
        db.executemany("insert into user_quests values (?, ?, ?, ?)", [(1, 1, 2, 1), (1, 12, 2, 1), (2, 22, 1, 0)])
        db.commit(); db.close()
        tables = {"MainQuestChapter": [{"MainQuestChapterId": c, "MainQuestSequenceGroupId": c} for c in (1, 2, 3, 4)],
                  "MainQuestSequenceGroup": [{"MainQuestSequenceGroupId": c, "MainQuestSequenceId": c * 10} for c in (1, 2, 3, 4)],
                  "MainQuestSequence": [{"MainQuestSequenceId": 10, "QuestId": 1}, {"MainQuestSequenceId": 30, "QuestId": 12},
                                        {"MainQuestSequenceId": 40, "QuestId": 22}]}
        self.patches[-1].stop(); self.patches[-2].stop()  # the real functions
        with mock.patch.object(cal, "table", lambda name: tables.get(name, [])):
            self.assertEqual(cal.reached_chapters(), {1, 3})
            self.assertEqual(cal.all_chapters(), {1, 2, 3, 4})
        self.patches[-1].start(); self.patches[-2].start()

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



    def test_the_game_forgets_its_day_markers_when_its_clock_goes_back(self):
        reset = cal.client_days_file()
        self.assertEqual(reset.parent, self.dir / "saves")  # beside the save, where the launchers look
        state = self.state()
        # Showing original dates moves the clock back by the loop's offset.
        cal.set_original_dates(state, True)
        self.assertTrue(reset.exists())
        reset.unlink()
        # Back to this loop's dates: forward, the markers stay.
        cal.set_original_dates(state, False)
        self.assertFalse(reset.exists())
        # Turning the calendar off after a jump ahead: back to real time.
        cal.write_state(dict(state, jumpMillis=100 * WEEK))
        cal.turn_off()
        self.assertTrue(reset.exists())
        reset.unlink()
        # Off from a calendar at real time: no change.
        cal.write_state(self.state())
        cal.turn_off()
        self.assertFalse(reset.exists())


class MissedText(unittest.TestCase):
    """What a jump skips, as the Jump to page lists it."""
    def test_lists_only_what_is_missed_with_singular_and_plural(self):
        self.assertEqual(cal.missed_text({"event": 10, "summon": 11, "shop": 13, "arena": 1}),
                         "10 events, 11 summons, 13 shops, 1 Arena season")
        self.assertEqual(cal.missed_text({"pass": 1, "event": 1}), "1 event, 1 monthly pass")
        self.assertEqual(cal.missed_text({"arena": 2}), "2 Arena seasons")
        self.assertEqual(cal.missed_text({}), "")


if __name__ == "__main__":
    unittest.main()
