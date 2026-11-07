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

    def force(self, r, raises):
        return r.force + 1000 * len(raises)

    def raisable(self, r):
        return {35036}

    def opponents(self):
        return [{"id": 9000001, "name": "Operator 6O", "points": 5140, "costumes": [31032, 35036, 33029]}]

    def slots(self):
        return [{"deck_type": 2, "number": 1, "label": "Arena deck 1 (defense)", "summary": "Marie, Sarafa, Rion"},
                {"deck_type": 2, "number": 2, "label": "Arena deck 2", "summary": None}]

    def players(self):
        return [(1, "2B")]

    # Subjugation
    def bosses(self):
        return [{"id": 1, "name": "Fiery Cursed God", "element": "fire"}, {"id": 5, "name": "Bleak Cursed God", "element": "dark"}]

    def subjugation(self, boss_id, difficulty, criteria):
        self.asked = (boss_id, difficulty, criteria.mode.kind)
        return [self.loadout]

    @property
    def loadout(self):
        deck = lambda i, lineup, dmg: SimpleNamespace(lineup=lineup, name=f"deck {i}", strategy="Team Dauntless", elements=("fire",) * 3,
                                                      equipped=SimpleNamespace(specs=SPECS, to_add=[]), deck=None, force=400000,
                                                      phase=i, damage=dmg, knockdowns=1, standing=3)
        return SimpleNamespace(key="b1d5:1,2,3|4,5,6|7,8,9", rank=1, boss_id=1, difficulty=5, damage=300,
                               force=1200000, decks=[deck(1, (1, 2, 3), 150), deck(2, (4, 5, 6), 100), deck(3, (7, 8, 9), 50)])

    def find_loadout(self, key):
        return self.loadout if key == self.loadout.key else None

    def loadout_detail(self, lo):
        return {"kind": "subjugation", "decks": [], "raises": [], "added": 0}

    def loadout_force(self, lo, raises):
        return [400000, 400000, 400000]

    def loadout_raisable(self, lo):
        return {35036}


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

    def test_criteria_are_a_closed_popup_behind_filters(self):
        """As the mockup: the criteria open from the Filters button, closed at first, at any width."""
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn('id="filters-panel" role="dialog" aria-modal="true" aria-label="Filters" hidden', html)
        self.assertIn('class="open-filters', html)
        self.assertNotIn('bracket-header">Criteria', html)
        self.assertNotIn(".open-filters,.sheet-head,.sheet-foot{display:none}", html)

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

    def test_a_broken_session_is_rebuilt_once(self):
        """A database error (the save changed under it) drops the session and the request runs again on a new one."""
        import sqlite3
        broken, fresh = FakeSession(), self.session
        broken.page = lambda *a: (_ for _ in ()).throw(sqlite3.DatabaseError("database disk image is malformed"))
        made = [broken, fresh]
        dropped = []
        with mock.patch.object(db, "session", lambda user: made[0]), \
             mock.patch.object(db, "drop_session", lambda user: (dropped.append(user), made.pop(0))):
            r = self.c.get("/decks/results", params={"user": 1, "offset": 0, "limit": 6})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total"], 18640)
        self.assertEqual(dropped, [1])

    def test_card_says_its_strategy_and_whether_experts_picked_it(self):
        [card] = self.c.get("/decks/results", params={"user": 1, "offset": 0, "limit": 6}).json()["items"]
        self.assertEqual(card["strategy"], "Compromise counter")
        self.assertIs(card["expert"], False)

    def test_card_names_each_costume_under_its_portrait_and_not_the_count_to_add(self):
        html = self.c.get("/decks", params={"user": 1}).text
        card = html[html.index("function cardHtml"):html.index("async function load")]
        self.assertIn('<div class="tile"><div class="por', card)
        self.assertIn('<span class="nm">${esc(t.name)}</span></div>', card)
        self.assertNotIn("to add", card)
        [item] = self.c.get("/decks/results", params={"user": 1, "offset": 0, "limit": 6}).json()["items"]
        self.assertTrue(all(t["name"] for t in item["tiles"]))

    def test_sort_sits_in_the_result_bar_instead_of_the_criteria_summary(self):
        html = self.c.get("/decks", params={"user": 1}).text
        bar = html[html.index('<div class="resbar">'):html.index('<div class="cards"')]
        self.assertIn('<select id="sort"', bar)
        for v, n in (("match", "Best match"), ("force", "Force"), ("fewest", "Fewest to add")):
            self.assertIn(f'<option value="{v}">{n}</option>', bar)
        self.assertNotIn('id="ctx"', html)
        self.assertNotIn('data-name="sort"', html)

    def test_no_data_pick_text(self):
        html = self.c.get("/decks", params={"user": 1}).text
        for text in ("Data pick", "data_pick", 'id="d-pick"', ".badge"):
            self.assertNotIn(text, html)

    def test_the_mode_is_called_all_maxed(self):
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn('<button type="button" data-v="best" class="on">All maxed</button>', html)
        self.assertNotIn("Theoretical", html)

    def test_all_maxed_ticks_every_raise(self):
        """All maxed counts the player's own costumes and characters fully raised, so the write raises them
        unless unticked; What I own leaves them unticked."""
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn('if (state.mode === "best") document.querySelectorAll("#w-raise input").forEach(b => (b.checked = true));', html)
        self.assertIn('"mythic_slab": "Mythic Slab"', html)

    def test_subjugation_is_a_mode_with_a_boss_and_difficulty(self):
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn('<button type="button" data-v="subjugation">Subjugation</button>', html)
        self.assertIn('<option value="1">Fiery Cursed God · fire</option>', html)
        self.assertIn('<select id="difficulty">', html)

    def test_subjugation_results_are_loadouts_of_three_decks(self):
        r = self.c.get("/decks/results", params={"user": 1, "deck_for": "subjugation", "boss": 1, "difficulty": 5, "mode": "best"}).json()
        self.assertEqual(self.session.asked, (1, 5, "best"))
        [card] = r["items"]
        self.assertEqual((card["kind"], card["damage"], r["exhausted"]), ("subjugation", 300, True))
        self.assertEqual([d["phase"] for d in card["decks"]], [1, 2, 3])
        self.assertEqual([d["damage"] for d in card["decks"]], [150, 100, 50])
        self.assertEqual(len(card["decks"][0]["tiles"]), 3)
        more = self.c.get("/decks/results", params={"user": 1, "deck_for": "subjugation", "boss": 1, "offset": 6}).json()
        self.assertEqual(more["items"], [])

    def test_the_session_caches_subjugation_by_criteria(self):
        """The real Session (not the fake): its cache key holds the criteria's minimum stats (a dict)."""
        from deckbuilder import bighunt, subjugation
        boss = SimpleNamespace(id=1, fights={5: object()})
        stub = SimpleNamespace(tables=None, gen=None, _subjugation={}, loadouts={})
        lo = self.session.loadout
        runs = []
        with mock.patch.object(bighunt, "boss", lambda tables, i: boss), \
             mock.patch.object(subjugation, "rank", lambda *a, **kw: runs.append(1) or [lo]):
            c = db.criteria_from(None, {"deck_for": "subjugation", "min_agi": "1000"})
            self.assertEqual(db.Session.subjugation(stub, 1, 5, c), [lo])
            self.assertEqual(db.Session.subjugation(stub, 1, 5, db.criteria_from(None, {"min_agi": "1000"})), [lo])
        self.assertEqual(len(runs), 1)
        self.assertIs(stub.loadouts[lo.key], lo)

    def test_a_loadout_writes_the_three_subjugation_decks(self):
        """One Save Data snapshot, then each deck to its Subjugation deck (101, 102, 103), its own raises only."""
        r = self.c.post("/decks/write", json={"user": 1, "key": self.session.loadout.key, "raise": [35036]}).json()
        self.assertEqual(r["ok"], True)
        self.assertEqual([c[0] for c in self.calls], ["backup", "shim", "shim", "shim"])
        slots = [c[1]["deck"]["slots"] for c in self.calls[1:]]
        self.assertEqual(slots, [[{"deck_type": 5, "number": n, "power": 400000}] for n in (101, 102, 103)])
        self.assertEqual(r["slots"], [101, 102, 103])

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

    def test_prepare_builds_the_stage_and_keeps_the_game_playing(self):
        seen = []
        with mock.patch.object(db, "prepare", lambda user, against=None: seen.append((user, against))):
            r = self.c.post("/decks/prepare", json={"user": 1, "against": "9000001"})
        self.assertEqual((r.status_code, r.json()["ok"], seen), (200, True, [(1, "9000001")]))
        self.assertEqual(r.headers.get("x-bunker-keep-playing"), "1")

    def test_routes_ask_for_prepare_when_the_stage_is_not_ready(self):
        def not_ready(user):
            raise db.StageNotReady()
        with mock.patch.object(db, "session", not_ready):
            r = self.c.get("/decks/results", params={"user": 1})
            self.assertEqual((r.status_code, r.json()["prepare"]), (409, True))
            for path in ("/decks/detail", "/decks/rescore"):
                self.assertEqual(self.c.get(path, params={"user": 1, "key": "x"}).status_code, 409, path)
            page = self.c.get("/decks", params={"user": 1})
            self.assertEqual(page.status_code, 200)
            self.assertIn("/decks/prepare", page.text)

    def test_write_validates_the_request(self):
        key = db.result_key(self.session.result)
        bad = [{"user": 1, "key": key, "slots": [16]}, {"user": 1, "key": key, "slots": [0]},
               {"user": 1, "key": key, "slots": [2], "raise": [99999]}, {"user": "two", "key": key, "slots": [2]}]
        for body in bad:
            self.assertEqual(self.c.post("/decks/write", json=body).status_code, 400, body)
        self.assertEqual(self.calls, [])

    def test_write_computes_force_without_simulating(self):
        self.session.rescore = lambda r, raises: self.fail("a write simulated fights")
        r = self.c.post("/decks/write", json={"user": 1, "key": db.result_key(self.session.result), "slots": [2], "raise": [35036]})
        self.assertEqual(r.json()["ok"], True)
        self.assertEqual(self.calls[1][1]["deck"]["slots"][0]["power"], 413318)

    def test_portraits(self):
        """Costume portraits from the game's own files, converted like the Archive's images."""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        bundle = tmp / "assetbundle/ui/costume/ch013012/ch013012_portrait.assetbundle"
        bundle.parent.mkdir(parents=True)
        bundle.write_bytes(b"bundle")
        made = []

        def convert(src, target, size):
            made.append((Path(src).name, size))
            Path(target).write_bytes(b"\x89PNG\r\n\x1a\nfake")
            return ""
        names = {35035: {"costume_actor_asset_id": "ch013012"}}
        with mock.patch.object(db, "_portrait_source", lambda: (tmp, convert)), \
             mock.patch.object(db, "_portrait_cache", lambda: tmp / "cache"), \
             mock.patch.object(db, "_costume_asset", lambda cid: names.get(cid, {}).get("costume_actor_asset_id")):
            r = self.c.get("/decks/portrait/35035.png")
            self.assertEqual((r.status_code, r.headers["content-type"]), (200, "image/png"))
            self.assertTrue(r.content.startswith(b"\x89PNG"))
            self.c.get("/decks/portrait/35035.png")
            self.assertEqual(made, [("ch013012_portrait.assetbundle", 360)])     # converted once, then kept
            self.assertEqual(self.c.get("/decks/portrait/99999.png").status_code, 404)
        with mock.patch.object(db, "_portrait_source", lambda: None):
            self.assertEqual(self.c.get("/decks/portrait/35035.png").status_code, 404)

    def test_piece_icons(self):
        """A piece's icon (weapon, companion, memoir, debris) from the game's files, as the notices show it."""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        bundle = tmp / "assetbundle/ui/weapon/wp001060/wp001060_standard.assetbundle"
        bundle.parent.mkdir(parents=True)
        bundle.write_bytes(b"bundle")

        def convert(src, target, size):
            Path(target).write_bytes(b"\x89PNG\r\n\x1a\nfake")
            return ""
        paths = {("weapon", 100001): "ui/weapon/wp001060/wp001060_standard.assetbundle"}
        with mock.patch.object(db, "_portrait_source", lambda: (tmp, convert)), \
             mock.patch.object(db, "_portrait_cache", lambda: tmp / "cache"), \
             mock.patch.object(db, "_icon_asset", lambda kind, pid: paths.get((kind, pid))):
            r = self.c.get("/decks/icon/weapon/100001.png")
            self.assertEqual((r.status_code, r.headers["content-type"]), (200, "image/png"))
            self.assertEqual(self.c.get("/decks/icon/weapon/5.png").status_code, 404)
            self.assertEqual(self.c.get("/decks/icon/costume/100001.png").status_code, 404)

    def test_page_shows_portraits(self):
        page = (ROOT / "overlays/python/web/templates/deck_builder.html").read_text()
        self.assertIn("/decks/portrait/", page)

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
