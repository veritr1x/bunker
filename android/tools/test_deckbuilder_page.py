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
        return [{"deck_type": 2, "number": 1, "label": "Arena deck 1 (defense)", "summary": "Marie, Sarafa, Rion", "defense": True},
                {"deck_type": 2, "number": 2, "label": "Arena deck 2", "summary": None},
                {"deck_type": 1, "number": 3, "label": "Loadout deck 3", "summary": "Fio, Saryu, Lars"}]

    def players(self):
        return [(1, "2B")]

    def costumes(self, mode):
        self.costumes_mode = mode
        return [{"id": 35036, "name": "New Year's Belle Sarafa", "character": "Sarafa", "element": "dark"},
                {"id": 33029, "name": "Oathbound Exile Rion", "character": "Rion", "element": "wind"}]

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
        # the Programs page's grid, as the player sees it (in English)
        import jinja2
        import bunker_text
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(templates)), autoescape=True)
        bunker_text.install(env)
        home = env.get_template("index.html").render(game_db_exists=True, active="home", message="", error="")
        self.assertIn('<a href="/decks">Deck Builder <span>', home)
        self.assertIn("android_deckbuilder", (ROOT / "android/app/src/main/python/android_runtime.py").read_text())

    def test_page_renders(self):
        r = self.c.get("/decks", params={"user": 1})
        self.assertEqual(r.status_code, 200)
        for text in ("Deck Builder", 'data-name="Arena deck 1"', "Operator 6O", "/decks/results"):
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

    def test_what_i_own_can_allow_any_number_of_added_pieces(self):
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn('<option value="20">20</option><option value="all">All</option>', html)
        c = db.criteria_from(None, {"mode": "owned", "allow": "all"})
        self.assertEqual((c.mode.kind, c.mode.allow_missing), ("owned", db.ALLOW_ALL))
        self.assertEqual(db.criteria_from(None, {"mode": "owned", "allow": "5"}).mode.allow_missing, 5)

    def test_the_switches_are_even_grids_across_the_panel(self):
        """Attack and Defense take equal halves with Subjugation across below; every switch spans the panel, its
        buttons bare of the browser's own look (iOS insets a selected button)."""
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn(".seg{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);width:100%;border:1px solid currentColor}", html)
        self.assertIn("-webkit-appearance:none;appearance:none;margin:0;border-radius:0;box-shadow:none", html)
        self.assertIn('.seg[data-name="deck_for"]{grid-auto-flow:row;grid-template-columns:repeat(2,minmax(0,1fr))}', html)
        self.assertIn('.seg[data-name="deck_for"] [data-v="subjugation"]{grid-column:1/-1;border-left:0;border-top:1px solid currentColor}', html)
        self.assertNotIn(".page-side .seg{display:flex}", html)

    def test_the_allow_menu_shows_only_with_what_i_own(self):
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn('<p class="help owned-only">Allow up to', html)
        self.assertIn('<details class="info best-only"><summary aria-label="More information">i</summary><div>Ranks decks as if you owned every costume', html)
        self.assertIn('<details class="info owned-only"><summary aria-label="More information">i</summary><div>Uses your costumes as they are.</div>', html)
        self.assertIn('body.owned .best-only,body:not(.owned) .owned-only{display:none!important}', html)
        self.assertIn('document.body.classList.toggle("owned", state.mode === "owned");', html)

    def test_filters_pick_characters_to_include_or_leave_out(self):
        """The costumes Deck Builder draws from, for the mode; tapping one requires it, again leaves it out."""
        r = self.c.get("/decks/costumes", params={"user": 1, "mode": "owned"}).json()
        self.assertEqual(self.session.costumes_mode, "owned")
        self.assertEqual([c["id"] for c in r], [35036, 33029])
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn('<div class="f-chars" id="f-chars"', html)
        self.assertIn('<input type="search" id="f-find"', html)
        self.assertIn('include: state.include.join(","), exclude: state.exclude.join(",")', html)
        self.assertNotIn("from its deck card's detail", html)
        c = db.criteria_from(None, {"include": "35036", "exclude": "33029,34048"})
        self.assertEqual((set(c.include), set(c.exclude)), ({35036}, {33029, 34048}))

    def test_a_required_costume_not_yet_staged_is_prepared(self):
        """All maxed with a required costume the stage lacks: the reply asks to prepare it, and prepare stages it."""
        def page(criteria, offset, limit):
            raise db.StageNotReady(extra=(31001,))
        self.session.page = page
        r = self.c.get("/decks/results", params={"user": 1, "include": "31001"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual((r.json()["prepare"], r.json()["costumes"]), (True, [31001]))
        asked = []
        with mock.patch.object(db, "prepare", lambda user, against=None, costumes=(): asked.append((against, list(costumes)))):
            ok = self.c.post("/decks/prepare", json={"user": 1, "costumes": [31001]}).json()
        self.assertEqual((ok["ok"], asked), (True, [(None, [31001])]))
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn("await prepare(r.against, r.costumes)", html)

    def test_the_picker_lists_every_costume_in_one_list(self):
        """One list, by character then costume: no split between Deck Builder's pool and the rest."""
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertNotIn("f-sep", html)
        self.assertNotIn("Every other costume", html)
        names = {33029: "Oathbound Exile Rion", 35036: "New Year's Belle Sarafa", 31032: "Yuletide Songstress Marie"}
        chars = {33029: "Rion", 35036: "Sarafa", 31032: "Marie"}
        stub = SimpleNamespace(gen=SimpleNamespace(pool=lambda mode: [35036, 33029]), base=None,
                               tables=SimpleNamespace(idx=lambda *a: {c: {} for c in names}, is_fieldable=lambda c: True,
                                                      costume_name=names.get, character_name=chars.get, costume_element=lambda c: "dark"))
        listed = [c["id"] for c in db.Session.costumes(stub, "best")]
        self.assertEqual(listed, [31032, 33029, 35036])        # Marie, Rion, Sarafa

    def test_filter_chips_keep_their_text_when_hovered(self):
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn(".chip:hover:not(.on){background:color-mix(in srgb,var(--fg-dark) 8%,transparent)!important;color:inherit!important}", html)

    def test_the_mode_is_called_all_maxed(self):
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn('<button type="button" data-v="best" class="on">All maxed</button>', html)
        self.assertNotIn("Theoretical", html)

    def test_all_maxed_ticks_every_raise(self):
        """All maxed counts the player's own costumes and characters fully raised, so the write raises them
        unless unticked; What I own leaves them unticked."""
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn('if (state.mode === "best") document.querySelectorAll("#w-raise input").forEach(b => (b.checked = true));', html)
        self.assertIn('"mythic_slab": "Mythic Slab"', html)   # the catalogue's words, in TXT.field

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
        stub = SimpleNamespace(tables=None, gen=None, _subjugation={}, loadouts={}, _staged=lambda criteria: None)
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

    def test_write_to_a_loadout_deck(self):
        """A Loadout (quest) deck is a write target too: {deck_type, number}; a bare number is an Arena deck."""
        key = db.result_key(self.session.result)
        r = self.c.post("/decks/write", json={"user": 1, "key": key, "slots": [{"deck_type": 1, "number": 3}, 2], "raise": []})
        self.assertEqual(r.json()["ok"], True, r.json())
        self.assertEqual(self.calls[1][1]["deck"]["slots"], [{"deck_type": 1, "number": 3, "power": 412318},
                                                             {"deck_type": 2, "number": 2, "power": 412318}])
        for bad in ({"deck_type": 3, "number": 1}, {"deck_type": 1, "number": 16}, {"deck_type": 1}, "1:3"):
            self.assertEqual(self.c.post("/decks/write", json={"user": 1, "key": key, "slots": [bad]}).status_code, 400, bad)

    def test_a_deck_shows_its_win_rate(self):
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn("<b>${c.win_pct}%</b><small>${esc(TXT.winRateShort)}</small>", html)
        self.assertIn('winRateShort: "win rate"', html)
        self.assertIn('[[TXT.winRate, c.win_pct + "%"]', html)
        self.assertIn('winRate: "Win rate"', html)

    def test_write_opens_the_deck_picker(self):
        """The deck list appears only after WRITE DECK: Arena and Loadout decks on tabs, each deck a tile naming what
        it holds; the picks are listed as what they replace before REPLACE writes."""
        html = self.c.get("/decks", params={"user": 1}).text
        self.assertIn('onclick="openPick()">WRITE DECK</button>', html)
        self.assertIn('<div id="w-pick" hidden>', html)
        self.assertIn('<button type="button" data-t="2" class="on">Arena</button><button type="button" data-t="1">Loadout</button>', html)
        self.assertIn('<label class="wp-sl" data-t="1" hidden><input type="checkbox" value="1:3" data-name="Loadout deck 3" data-summary="Fio, Saryu, Lars">', html)
        self.assertIn('<b>03</b><span>Fio, Saryu, Lars</span>', html)
        self.assertIn('<i>Defense</i>', html)
        self.assertIn('fill(TXT.replaces, {deck: b.dataset.name, summary: b.dataset.summary})', html)
        self.assertIn('replaces: "Replaces {deck} ({summary})"', html)
        self.assertIn('id="w-yes" onclick="writeDeck()" disabled>REPLACE</button>', html)
        self.assertNotIn('id="w-to"', html)      # no deck list in the deck view itself
        self.assertNotIn("preTick", html)        # nothing is ticked for you: the deck is the one you pick
        self.assertIn("#w-go[hidden]{display:none}", html)     # the button style would show it

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
        with mock.patch.object(db, "prepare", lambda user, against=None, costumes=(): seen.append((user, against))):
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
        self.assertEqual(len(slots), 30)


if __name__ == "__main__":
    unittest.main()
