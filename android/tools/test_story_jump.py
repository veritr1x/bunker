#!/usr/bin/env python3
"""Pod Programs › Story Jump: the Original calendar opening the chapter a save
was jumped to (android_calendar.py) and the page (android_story.py), with the
editing shim, backups and game data builds stubbed. Needs the Android Python
requirements."""
from pathlib import Path
import sqlite3, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "android/app/src/main/python"))
import android_calendar as cal  # noqa: E402
from web import config  # noqa: E402

# Chapter 15 is quest 301; chapter 16 is quests 305-306 (scenes 611, 612...).
TABLES = {
    "MainQuestSequence": [{"QuestId": 301, "MainQuestSequenceId": 15}, {"QuestId": 305, "MainQuestSequenceId": 16},
                          {"QuestId": 306, "MainQuestSequenceId": 16}],
    "MainQuestSequenceGroup": [{"MainQuestSequenceId": 15, "MainQuestSequenceGroupId": 15},
                               {"MainQuestSequenceId": 16, "MainQuestSequenceGroupId": 16}],
    "MainQuestChapter": [{"MainQuestSequenceGroupId": 15, "MainQuestChapterId": 15},
                         {"MainQuestSequenceGroupId": 16, "MainQuestChapterId": 16}],
    "QuestScene": [{"QuestSceneId": 600, "QuestId": 301}, {"QuestSceneId": 611, "QuestId": 305},
                   {"QuestSceneId": 620, "QuestId": 306}],
}


def make_save(path, cleared, head):
    db = sqlite3.connect(path)
    db.executescript("""
        create table user_quests (user_id integer, quest_id integer, clear_count integer);
        create table user_main_quest (user_id integer, head_quest_scene_id integer);
    """)
    db.executemany("insert into user_quests values (1, ?, 1)", [(q,) for q in cleared])
    db.execute("insert into user_main_quest values (1, ?)", (head,))
    db.commit()
    db.close()


class CalendarReach(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(config, "GAME_DB_PATH", self.dir / "game.db"),
                        mock.patch.object(cal, "table", lambda name: TABLES.get(name, []))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_story_position_counts_as_reached(self):
        make_save(config.GAME_DB_PATH, [301], 611)
        self.assertEqual(cal.reached_chapters(), {15, 16})

    def test_no_save(self):
        self.assertEqual(cal.reached_chapters(), set())


class Reopen(unittest.TestCase):
    def run_with(self, state):
        calls = []
        with mock.patch.object(cal, "read_state", lambda: state), \
                mock.patch.object(cal, "activate_loop", lambda s: calls.append("loop")), \
                mock.patch.object(cal, "build_view", lambda s: calls.append("view")):
            return cal.reopen_reached_chapters(), calls

    def test_calendar_off(self):
        self.assertEqual(self.run_with(None), (False, []))

    def test_first_loop(self):
        self.assertEqual(self.run_with({"loopStart": 1, "loop": 1}), (True, ["loop"]))

    def test_first_loop_with_original_dates(self):
        self.assertEqual(self.run_with({"loopStart": 1, "loop": 1, "originalDates": True}), (True, ["loop", "view"]))

    def test_later_loop(self):
        self.assertEqual(self.run_with({"loopStart": 1, "loop": 2}), (False, []))


# A story for the page: route 1 (chapter 1: q1 q2), season 2 route 2
# (chapter 15: q301, chapter 16: q305 q306) or route 3 (chapter 23: q401),
# season 3 route 4 (chapter 31: q500).
PAGE_TABLES = {
    "MainQuestRoute": [{"MainQuestRouteId": 1, "MainQuestSeasonId": 1, "SortOrder": 1},
                       {"MainQuestRouteId": 2, "MainQuestSeasonId": 2, "SortOrder": 1},
                       {"MainQuestRouteId": 3, "MainQuestSeasonId": 2, "SortOrder": 2},
                       {"MainQuestRouteId": 4, "MainQuestSeasonId": 3, "SortOrder": 1}],
    "MainQuestChapter": [{"MainQuestChapterId": c, "MainQuestRouteId": r, "SortOrder": o, "MainQuestSequenceGroupId": c}
                         for c, r, o in ((1, 1, 1), (15, 2, 1), (16, 2, 2), (23, 3, 1), (31, 4, 1))],
    "MainQuestSequenceGroup": [{"MainQuestSequenceGroupId": c, "DifficultyType": 1, "MainQuestSequenceId": c} for c in (1, 15, 16, 23, 31)]
                              + [{"MainQuestSequenceGroupId": 16, "DifficultyType": 2, "MainQuestSequenceId": 1016}],
    "MainQuestSequence": [{"MainQuestSequenceId": s, "SortOrder": o, "QuestId": q}
                          for s, o, q in ((1, 1, 1), (1, 2, 2), (15, 1, 301), (16, 1, 305), (16, 2, 306), (23, 1, 401),
                                          (31, 1, 500), (1016, 1, 10305))],
    "QuestScene": [{"QuestSceneId": q * 2, "QuestId": q, "SortOrder": q * 2} for q in (1, 2, 301, 305, 306, 401, 500)],
}


class Page(unittest.TestCase):
    def setUp(self):
        import android_story as story
        self.story = story
        self.dir = Path(tempfile.mkdtemp())
        self.calls = []
        self.shim_reply = {"ok": True, "applied": 2, "data": {"cleared": [305, 306], "grants": [
            {"possession_type": 3, "possession_id": 4, "count": 1}], "gems": 300, "dry_run": False}}

        def shim(payload):
            self.calls.append(("shim", payload["action"], payload["story"]))
            if isinstance(self.shim_reply, Exception):
                raise self.shim_reply
            return self.shim_reply

        def backup():
            self.calls.append(("backup",))
            return "backup_x_story jump.db"

        def reopen():
            self.calls.append(("reopen",))
            if isinstance(self.reopen, Exception):
                raise self.reopen
            return self.reopen
        self.reopen = True
        self.patches = [mock.patch.object(config, "GAME_DB_PATH", self.dir / "game.db"),
                        mock.patch.object(cal, "table", lambda name: PAGE_TABLES.get(name, [])),
                        mock.patch.object(story, "_shim", shim),
                        mock.patch.object(story, "_backup", backup),
                        mock.patch.object(story, "_name", lambda t, i: f"name {t}/{i}"),
                        mock.patch.object(cal, "reopen_reached_chapters", reopen)]
        for p in self.patches:
            p.start()
        make_save(config.GAME_DB_PATH, [1, 2, 301], 305 * 2)

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_jump_backs_up_first(self):
        out = self.story.jump(1, 500, 2)
        # A trial run first (it refuses before anything is written), then the backup, then the jump.
        self.assertEqual([c[0] for c in self.calls], ["shim", "backup", "shim", "reopen"])
        self.assertEqual(self.calls[0][1:], ("story_jump", {"quest_id": 500, "season2_route": 2, "dry_run": True}))
        self.assertEqual(self.calls[2][1:], ("story_jump", {"quest_id": 500, "season2_route": 2, "dry_run": False}))
        self.assertTrue(out["ok"])
        self.assertEqual(out["calendar"], "rebuilt")
        self.assertEqual(out["backup"], "backup_x_story jump.db")

    def test_preview_writes_nothing(self):
        self.shim_reply["data"]["dry_run"] = True
        out = self.story.preview(1, 500, 2)
        self.assertEqual(self.calls, [("shim", "story_jump", {"quest_id": 500, "season2_route": 2, "dry_run": True})])
        self.assertEqual(out["cleared_count"], 2)
        self.assertEqual(out["chapters"], "16")
        self.assertEqual(out["gems"], 300)
        self.assertEqual(out["grants"], [{"kind": "Companion", "name": "name 3/4", "count": 1}])

    def test_refusal_surfaces(self):
        self.shim_reply = self.story.StoryError("the save is already at or past that point")
        with self.assertRaisesRegex(self.story.StoryError, "already at or past"):
            self.story.jump(1, 2, 2)
        self.assertNotIn(("reopen",), self.calls)
        self.assertNotIn(("backup",), self.calls)  # a refused jump leaves no backup behind

    def test_calendar_failure_keeps_jump(self):
        self.reopen = RuntimeError("disk full")
        out = self.story.jump(1, 500, 2)
        self.assertTrue(out["ok"])
        self.assertTrue(out["calendar"].startswith("failed"), out["calendar"])

    def test_calendar_not_needed(self):
        self.reopen = False
        self.assertEqual(self.story.jump(1, 500, 2)["calendar"], "not needed")

    def test_chapters_states(self):
        view = self.story.chapters(1)
        self.assertEqual(view["route"], 2)
        rows = {c["id"]: c for s in view["seasons"] for c in s["chapters"]}
        self.assertEqual(rows[1]["state"], "cleared")
        self.assertEqual(rows[15]["state"], "cleared")
        self.assertEqual(rows[16]["state"], "here")
        self.assertEqual([(q["id"], q["state"]) for q in rows[16]["quests"]], [(305, "here"), (306, "ahead")])
        self.assertEqual(rows[31]["state"], "ahead")
        self.assertNotIn(23, rows)  # route 3 isn't shown while route 2 is picked
        route3 = {c["id"]: c for s in self.story.chapters(1, 3)["seasons"] for c in s["chapters"]}
        self.assertEqual(route3[23]["state"], "other")  # this save took route 2
        self.assertEqual(route3[31]["state"], "other")

    def test_page_renders(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(self.story.router)
        r = TestClient(app).get("/users/1/story")
        self.assertEqual(r.status_code, 200, r.text[:500])
        self.assertIn("Story Jump", r.text)
        self.assertIn("Jump to start", r.text)
        # counts take the forms the language uses (Intl.PluralRules), not a one/other pair
        self.assertIn("new Intl.PluralRules(", r.text)
        self.assertIn('gems: {"one": "{n} gem", "other": "{n} gems"}', r.text)

    def test_story_opens_the_player_in_use(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(self.story.router)
        import android_players
        with mock.patch.object(android_players, "device_player", lambda: 2):
            r = TestClient(app).get("/story", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/users/2/story")

    def test_preview_leaves_the_game_running(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import android_runtime
        app = FastAPI()
        app.include_router(self.story.router)
        self.shim_reply["data"]["dry_run"] = True
        r = TestClient(app).post("/users/1/story/preview", json={"quest_id": 500, "season2_route": 2})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(android_runtime.changed_game(r), "a preview sent the game back to its title screen")

    def test_routes_report_refusal(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(self.story.router)
        self.shim_reply = self.story.StoryError("the save is already at or past that point")
        r = TestClient(app).post("/users/1/story/jump", json={"quest_id": 2, "season2_route": 2})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {"ok": False, "error": "the save is already at or past that point"})


if __name__ == "__main__":
    unittest.main()
