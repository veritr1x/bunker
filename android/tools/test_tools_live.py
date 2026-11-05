#!/usr/bin/env python3
"""Pod Programs opens while the game keeps running. Pages that only show
things, and settings the server or game read later, work as they are; a change
to the save, the master data or the calendar stops the server for the change
and starts it again after, sending the game back to its title screen; a change
the game reads only as it launches first closes the game.
Needs fastapi."""
from pathlib import Path
import asyncio, json, sys, unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
import android_runtime  # noqa: E402
from fastapi import FastAPI  # noqa: E402


class Response:
    def __init__(self, status_code, body):
        self.status_code, self.body = status_code, body

    def json(self):
        return json.loads(self.body)


class Client:
    """Requests straight through the ASGI app, without an HTTP library."""
    def __init__(self, app):
        self.app = app

    def request(self, method, path):
        sent, out = [False], {"status": 0, "body": b""}

        async def receive():
            if sent[0]:
                return {"type": "http.disconnect"}
            sent[0] = True
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                out["status"] = message["status"]
            elif message["type"] == "http.response.body":
                out["body"] += message.get("body", b"")

        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http",
                 "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "", "headers": [],
                 "client": ("127.0.0.1", 1), "server": ("127.0.0.1", 80)}
        asyncio.run(self.app(scope, receive, send))
        return Response(out["status"], out["body"])

    def get(self, path):
        return self.request("GET", path)

    def post(self, path):
        return self.request("POST", path)


class Game:
    def __init__(self, live=True, error="", pause_error="", resume_error=""):
        self.live, self.error, self.closed = live, error, 0
        self.pause_error, self.resume_error, self.events = pause_error, resume_error, []

    def close(self):
        if self.error:
            return self.error
        self.closed += 1
        self.live = False
        return ""

    def pause(self):
        self.events.append("pause")
        return self.pause_error

    def resume(self):
        self.events.append("resume")
        return self.resume_error


CHANGES = ("/users/1/edit/items/grant", "/users/1/use", "/backups/restore", "/patcher/apply", "/patcher/calendar/on", "/something/new")


def client(game):
    app = FastAPI()
    calls = []

    def route(p):
        def handle():
            game.events.append(p)
            calls.append(p)
            if p == "/fails":
                raise RuntimeError("the change failed")
            return {"ok": True}
        return handle

    for path in ("/users/1/edit/items/grant", "/users/1/use", "/backups/restore", "/backups/create", "/patcher/apply",
                 "/patcher/calendar/on", "/patcher/calendar/view", "/patcher/calendar/off", "/patcher/calendar/timeline",
                 "/gacha", "/gacha/roulette", "/gacha/preset", "/display", "/something/new", "/fails"):
        app.post(path)(route(path))
    app.get("/users/1/edit/items")(lambda: {"page": True})
    android_runtime.install_game_guard(app, lambda: game.live, game.close, game.pause, game.resume)
    return Client(app), calls


class GameGuard(unittest.TestCase):
    def test_pages_and_later_settings_leave_the_game_running(self):
        game = Game()
        c, calls = client(game)
        self.assertEqual(c.get("/users/1/edit/items").status_code, 200)
        for path in ("/gacha", "/gacha/roulette", "/gacha/preset", "/display", "/patcher/calendar/timeline", "/backups/create"):
            self.assertEqual(c.post(path).status_code, 200, path)
        self.assertEqual(len(calls), 6)
        self.assertNotIn("pause", game.events)
        self.assertTrue(game.live)
        self.assertEqual(game.closed, 0)

    def test_changes_restart_the_server_around_them_and_the_game_plays_on(self):
        game = Game()
        c, calls = client(game)
        # Saves, players, restores, master data, the calendar, and anything not known to be safe.
        for path in CHANGES:
            self.assertEqual(c.post(path).status_code, 200, path)
        self.assertEqual(calls, list(CHANGES))
        self.assertEqual(game.events, [e for path in CHANGES for e in ("pause", path, "resume")])
        self.assertTrue(game.live)
        self.assertEqual(game.closed, 0)

    def test_the_server_starts_again_when_a_change_fails(self):
        game = Game()
        c, _ = client(game)
        try:
            c.post("/fails")
        except RuntimeError:
            pass
        self.assertEqual(game.events, ["pause", "/fails", "resume"])

    def test_a_failed_stop_refuses_the_change_and_says_why(self):
        game = Game(pause_error="The save could not be backed up")
        c, calls = client(game)
        r = c.post("/users/1/edit/items/grant")
        self.assertEqual((r.status_code, r.json()), (500, {"ok": False, "error": "The save could not be backed up"}))
        self.assertEqual(calls, [])
        self.assertEqual(game.events, ["pause"])

    def test_launch_only_changes_need_the_game_closed_first(self):
        game = Game()
        c, calls = client(game)
        for path in sorted(android_runtime.CLOSES):
            r = c.post(path)
            self.assertEqual(r.status_code, 409, path)
            self.assertTrue(r.json()["closeGame"], path)
            self.assertIn("closes the game", r.json()["error"])
        self.assertEqual(calls, [])
        self.assertEqual(game.closed, 0)

    def test_closing_the_game_lets_changes_through(self):
        game = Game()
        c, calls = client(game)
        self.assertEqual(c.get("/bunker/state").json(),
                         {"live": True, "safe": sorted(android_runtime.LIVE_SAFE), "closes": sorted(android_runtime.CLOSES)})
        r = c.post("/bunker/close-game")
        self.assertEqual((r.status_code, r.json()), (200, {"ok": True}))
        self.assertFalse(c.get("/bunker/state").json()["live"])
        self.assertEqual(c.post("/patcher/calendar/view").status_code, 200)
        self.assertEqual(calls, ["/patcher/calendar/view"])
        # Closing again is harmless.
        self.assertEqual(c.post("/bunker/close-game").json(), {"ok": True})
        self.assertEqual(game.closed, 1)

    def test_a_failed_close_says_why_and_changes_stay_refused(self):
        game = Game(error="The game could not be closed")
        c, calls = client(game)
        r = c.post("/bunker/close-game")
        self.assertEqual((r.status_code, r.json()), (500, {"ok": False, "error": "The game could not be closed"}))
        self.assertEqual(c.post("/patcher/calendar/view").status_code, 409)
        self.assertEqual(calls, [])

    def test_without_a_running_game_nothing_changes(self):
        game = Game(live=False)
        c, calls = client(game)
        self.assertEqual(c.post("/users/1/edit/items/grant").status_code, 200)
        self.assertEqual(c.post("/patcher/calendar/view").status_code, 200)
        self.assertEqual(c.post("/bunker/close-game").json(), {"ok": True})
        self.assertNotIn("pause", game.events)
        self.assertEqual(game.closed, 0)

    def test_the_message_after_a_change_says_how_it_reaches_the_game(self):
        live = android_runtime.game_live
        try:
            android_runtime.game_live = lambda: True
            self.assertIn("title screen", android_runtime.next_step())
            android_runtime.game_live = lambda: False
            self.assertIn("tap Deploy", android_runtime.next_step())
        finally:
            android_runtime.game_live = live

    def test_restore_is_offered_while_the_game_runs(self):
        # Lunar Base disables Restore while it finds the game server listening;
        # here the restore itself asks to close the game first.
        from web.services import backup_service
        backup_service.detect_lunar_tear_running = lambda: "lunar-tear gRPC server is listening on port 8003."
        android_runtime.adapt_services()
        self.assertFalse(backup_service.detect_lunar_tear_running())

    def test_every_page_carries_the_close_step(self):
        page = (root / "overlays/python/web/templates/base.html").read_text()
        self.assertIn("/bunker/close-game", page)
        self.assertIn("/bunker/state", page)
        # Only the launch-only changes ask to close the game.
        self.assertIn("s.closes", page)
        # Summon Rates names its buttons "action", which hides a form's action property.
        self.assertNotIn("form.action", page)


if __name__ == "__main__":
    unittest.main()


class SummonRatesForm(unittest.TestCase):
    """The page's own defaults must pass the browser's checks, or Save does nothing."""

    def test_default_values_fit_their_fields(self):
        import re
        from decimal import Decimal
        from jinja2 import Environment, FileSystemLoader
        import android_gacha
        env = Environment(loader=FileSystemLoader(str(root / "overlays/python/web/templates")))
        s = dict(android_gacha.DEFAULTS)
        page = env.get_template("gacha.html").render(request=None, active="gacha", settings=s, presets=android_gacha.PRESETS,
                                                     two_star=round(100 - s["fourStarPercent"] - s["threeStarPercent"], 3),
                                                     message="", error="", roulette=list(zip(android_gacha.ROULETTE_GEMS, android_gacha.ROULETTE_DEFAULTS)))
        fields = re.findall(r'<input type="number"[^>]*>', page)
        self.assertTrue(fields)
        for field in fields:
            step = re.search(r'step="([^"]+)"', field).group(1)
            value = re.search(r'value="([^"]*)"', field).group(1)
            if step == "any" or not value:
                continue
            self.assertEqual(Decimal(value) % Decimal(step), 0, field)
