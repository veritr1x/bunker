#!/usr/bin/env python3
"""Pod Programs › Deck Builder (android_deckbuilder.py): the page, results,
detail, opponents, write and rescore routes. Needs the Android Python
requirements and scripts/prepare.py (like test_gift.py)."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import deckbuilder_testlib  # noqa: F401  (paths)
from web import config  # noqa: E402
import android_deckbuilder as db  # noqa: E402
from deckbuilder import model  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def ref(kind, uuid, source):
    return model.PieceRef(kind, uuid, source)


SPECS = [model.CharacterSpec(ref("costume", "c1", "stage"), ref("weapon", "w1", "stage"), [ref("weapon", "w2", "save")], None,
                             [ref("memoir", "p1", "stage")], None),
         model.CharacterSpec(ref("costume", "c2", "save"), None, [], ref("companion", "k1", "save"), [], ref("debris", "t1", "stage")),
         None]


class FakeResult(SimpleNamespace):
    pass


def fake_result():
    eq = SimpleNamespace(specs=SPECS, overrides=[], reasons={(35036, "main_weapon"): "Best dark weapon."}, to_add=[SPECS[0].costume])
    return FakeResult(rank=1, lineup=(35036, 33029, 34048), name="Compromise counter", expert=False, strategy="compromise_counter",
                      win_rate=0.72, force=412318, to_add=1, tags=["Compromise", "Revive"], effects={"compromise"},
                      elements=("dark", "wind", "light"), stats=[{"agi": 1300}] * 3, why="Land Compromise first.", equipped=eq,
                      variants=[(33029, 35036, 34048)], data_pick=None, deck=None)


class FakeSession:
    def __init__(self):
        self.result = fake_result()
        self.raised = []
        self.gen = SimpleNamespace(added=len)

    def page(self, criteria, offset, limit):
        return SimpleNamespace(total=18640, items=[self.result][offset:offset + limit], exhausted=False, relax=None)

    def find(self, key):
        return self.result if key == db.result_key(self.result) else None

    def tiles(self, r):
        return [{"name": f"costume {c}", "element": e, "slot": s, "new": i == 0} for i, (c, e, s) in enumerate(zip(r.lineup, r.elements, "LMR"))]

    def detail(self, r):
        return {"title": r.name, "why_long": "It wins.", "characters": [], "overrides": [], "raises": [
            {"costume_id": 35036, "field": "level", "current": 90, "target": 100, "used_in": ["Arena deck 1"]}]}

    def rescore(self, r, raises):
        self.raised.append(list(raises))
        return {"force": r.force + 1000 * len(raises), "win_pct": 70 + len(raises)}

    def opponents(self):
        return [{"id": 9000001, "name": "Operator 6O", "points": 5140, "costumes": [31032, 35036, 33029]}]

    def slots(self):
        return [{"deck_type": 2, "number": 1, "label": "Arena deck 1 (defense)", "summary": "Marie, Sarafa, Rion"},
                {"deck_type": 2, "number": 2, "label": "Arena deck 2", "summary": None}]

    def players(self):
        return [(1, "2B")]


class PageTest(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        self.calls = []
        self.session = FakeSession()
        patches = [mock.patch.object(db, "session", lambda user: self.session),
                   mock.patch.object(db, "refresh_arena", lambda user: None),
                   mock.patch.object(db, "_backup", lambda: self.calls.append(("backup",))),
                   mock.patch.object(db, "_shim", lambda payload: self.calls.append(("shim", payload)) or {"ok": True, "applied": 1})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(db.router)
        self.c = TestClient(app)

    def test_nav_has_deck_builder(self):
        templates = ROOT / "overlays/python/web/templates"
        self.assertIn('href="/decks"', (templates / "base.html").read_text())
        self.assertIn('program("/decks", "Deck Builder"', (templates / "index.html").read_text())
        self.assertIn("android_deckbuilder", (ROOT / "android/app/src/main/python/android_runtime.py").read_text())

    def test_page_renders(self):
        r = self.c.get("/decks", params={"user": 1})
        self.assertEqual(r.status_code, 200)
        for text in ("Deck Builder", "Arena deck 1 (defense)", "Operator 6O", "/decks/results"):
            self.assertIn(text, r.text)

    def test_results_json_shape(self):
        r = self.c.get("/decks/results", params={"user": 1, "offset": 0, "limit": 6, "must": "compromise", "el_r": "water"}).json()
        self.assertEqual((r["total"], r["exhausted"], r["relax"]), (18640, False, None))
        [card] = r["items"]
        self.assertEqual(card["rank"], 1)
        self.assertEqual(card["win_pct"], 72)
        self.assertEqual(card["force"], 412318)
        self.assertEqual(card["to_add"], 1)
        self.assertEqual(card["variants"], 1)
        self.assertEqual([t["slot"] for t in card["tiles"]], ["L", "M", "R"])
        self.assertTrue(card["key"])

    def test_write_takes_snapshot_then_calls_shim(self):
        key = db.result_key(self.session.result)
        r = self.c.post("/decks/write", json={"user": 1, "key": key, "slots": [2], "raise": [35036]})
        self.assertEqual(r.json()["ok"], True)
        self.assertEqual([c[0] for c in self.calls], ["backup", "shim"])
        payload = self.calls[1][1]
        self.assertEqual(payload["action"], "deck_write")
        self.assertEqual(payload["deck"]["slots"], [{"deck_type": 2, "number": 2, "power": 413318}])
        self.assertEqual(payload["deck"]["raise"], [35036])
        first = payload["deck"]["characters"][0]
        self.assertEqual(first["costume"], {"uuid": "c1", "source": "stage"})
        self.assertEqual(first["subs"], [{"uuid": "w2", "source": "save"}])
        self.assertIsNone(payload["deck"]["characters"][2])
        self.assertNotIn("db_path", payload)
        self.assertNotIn("stage_path", payload)

    def test_write_refused_reason_shown(self):
        def refuse(payload):
            raise db.DeckBuilderError("not enough room for weapons: 5 more would pass the limit of 1000 (you hold 998)")
        with mock.patch.object(db, "_shim", refuse):
            r = self.c.post("/decks/write", json={"user": 1, "key": db.result_key(self.session.result), "slots": [2], "raise": []})
        self.assertEqual(r.status_code, 400)
        self.assertIn("not enough room for weapons", r.json()["error"])

    def test_write_needs_a_slot_and_a_known_deck(self):
        self.assertEqual(self.c.post("/decks/write", json={"user": 1, "key": "nope", "slots": [2]}).status_code, 404)
        self.assertEqual(self.c.post("/decks/write", json={"user": 1, "key": db.result_key(self.session.result), "slots": []}).status_code, 400)
        self.assertEqual(self.calls, [])

    def test_rescore_changes_with_raise(self):
        key = db.result_key(self.session.result)
        a = self.c.get("/decks/rescore", params={"user": 1, "key": key}).json()
        b = self.c.get("/decks/rescore", params={"user": 1, "key": key, "raise": "35036"}).json()
        self.assertNotEqual(a, b)
        self.assertEqual(self.session.raised, [[], [35036]])

    def test_page_and_write_refresh_the_arena_data(self):
        """Opening the page and writing a deck refresh the ladder's data
        (deck table when the master data changed, the player's score)."""
        seen = []
        with mock.patch.object(db, "refresh_arena", lambda user: seen.append(user)):
            self.c.get("/decks", params={"user": 1})
            self.c.post("/decks/write", json={"user": 1, "key": db.result_key(self.session.result), "slots": [2], "raise": []})
        self.assertEqual(seen, [1, 1])

    def test_detail(self):
        r = self.c.get("/decks/detail", params={"user": 1, "key": db.result_key(self.session.result)}).json()
        self.assertEqual(r["raises"][0]["used_in"], ["Arena deck 1"])

    def test_page_stale_or_missing_piece(self):
        """A save deck naming a costume the player no longer owns: the slot still lists."""
        import json
        from deckbuilder_testlib import FIX
        con = model.rows_to_db(json.loads((FIX / "saves" / "129f58f58f43.json").read_text()))
        con.execute("delete from user_costumes where costume_id=34012")
        tables = SimpleNamespace(character_name=lambda cid: "missing costume" if cid is None else f"costume {cid}")
        slots = model.slots(model.Save(con, 1), tables)
        self.assertEqual(len(slots), 15)


if __name__ == "__main__":
    unittest.main()
