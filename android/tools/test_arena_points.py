#!/usr/bin/env python3
"""Pod Programs › Players › Arena points (android_arena.py): the save is backed
up before the editing shim's "set_arena_points" (bunker_arena_points.go), out
of range points are refused before either, and the player page shows the
points the save holds. The shim and backups are stubbed. Needs the Android
Python requirements."""
from pathlib import Path
import json, sqlite3, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "android/app/src/main/python"))
from web import config  # noqa: E402


def make_save(path, data=None):
    db = sqlite3.connect(path)
    db.execute("create table user_bunker_ext (user_id integer primary key, data text not null default '{}')")
    if data is not None:
        db.execute("insert into user_bunker_ext values (1, ?)", (json.dumps(data),))
    db.commit()
    db.close()


class ArenaPoints(unittest.TestCase):
    def setUp(self):
        import android_arena as arena
        from web.services import backup_service
        self.arena = arena
        self.dir = Path(tempfile.mkdtemp())
        self.calls = []

        def shim(payload):
            self.calls.append(("shim", payload))
            return {"ok": True, "applied": 1, "data": {"point": payload["arena_points"], "season_id": 202037, "rank": 1}}

        def create_backup(reason="manual"):
            self.calls.append(("backup", reason))
            return mock.Mock(filename="backup_x_arena points.db")

        self.patches = [mock.patch.object(config, "GAME_DB_PATH", self.dir / "game.db"),
                        mock.patch.object(config, "find_master_data_bin", lambda: self.dir / "master.bin.e"),
                        mock.patch.object(arena, "_shim", shim),
                        mock.patch.object(backup_service, "create_backup", create_backup)]
        for p in self.patches:
            p.start()
        make_save(config.GAME_DB_PATH, {"pvp": {"point": 1234}})

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(self.arena.router)
        return TestClient(app)

    def test_set_points_backs_up_then_calls_shim(self):
        out = self.arena.set_points(1, 52000)
        self.assertEqual(self.calls, [
            ("backup", "arena points"),
            ("shim", {"action": "set_arena_points", "db_path": str(config.GAME_DB_PATH),
                      "master_data_path": str(self.dir / "master.bin.e"), "user_id": 1, "arena_points": 52000})])
        self.assertEqual(out, {"ok": True, "point": 52000, "rank": 1, "backup": "backup_x_arena points.db"})

    def test_out_of_range_refused_without_backup(self):
        for points in (-1, 1000000):
            with self.assertRaises(self.arena.ArenaError):
                self.arena.set_points(1, points)
        r = self.client().post("/users/1/arena-points", data={"points": "abc"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("error=", r.headers["location"])
        self.assertEqual(self.calls, [])

    def test_current_points_reads_save(self):
        self.assertEqual(self.arena.current_points(1), 1234)
        self.assertEqual(self.arena.current_points(2), 0)  # no row
        make_save(self.dir / "empty.db", {})
        self.assertEqual(self.arena.current_points(1, db_path=self.dir / "empty.db"), 0)
        self.assertEqual(self.arena.current_points(1, db_path=self.dir / "missing.db"), 0)

    def test_points_above_the_ladder_accepted(self):
        out = self.arena.set_points(1, 52136)  # one win past 52,049 on the iPad
        self.assertEqual(out["point"], 52136)

    def test_route_redirects_with_message(self):
        r = self.client().post("/users/1/arena-points", data={"points": "52000"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["location"].startswith("/users/1?message="), r.headers["location"])
        from urllib.parse import unquote_plus
        self.assertIn("52,000", unquote_plus(r.headers["location"]))

    def test_player_page_shows_points(self):
        from datetime import datetime
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import bunker_text
        bunker_text.install_everywhere()  # the page helpers the app installs at start-up (android_runtime.create_app)
        from web.routes import users
        from web.services.userdata_service import UserDetail
        detail = UserDetail(user_id=1, uuid="u", player_id=1, name="", message="", register_at=datetime(2026, 1, 1),
                            last_login_at=None, total_login_count=1, level=100, exp=0, paid_gem=0, free_gem=0,
                            inventory_counts=[], stackables=[])
        app = FastAPI()
        app.include_router(users.router)
        with mock.patch.object(users.userdata_service, "get_user_detail", lambda user_id: detail):
            r = TestClient(app).get("/users/1")
        self.assertEqual(r.status_code, 200, r.text[:500])
        self.assertIn("Arena points", r.text)
        self.assertIn('action="/users/1/arena-points"', r.text)
        self.assertIn('name="points" min="0" max="999999" step="1" value="1234"', r.text)


if __name__ == "__main__":
    unittest.main()
