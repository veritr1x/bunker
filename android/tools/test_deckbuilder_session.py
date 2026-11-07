#!/usr/bin/env python3
"""Pod Programs › Deck Builder's real Session (android_deckbuilder.Session) on
a real save file, with bunker-edit standing in for the Android bridge: threads,
opponents outside the stage, stage rebuilds and missing pieces."""
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from deckbuilder_testlib import BUILD, FIX, MASTER, MASTER_BIN, NAMES, cli_invoke, needs_stage
from web import config  # noqa: E402
import android_deckbuilder as db  # noqa: E402
from deckbuilder import generate, model  # noqa: E402

IPAD = "129f58f58f43"          # 20 costumes, quest deck 1/1 (34010, 34012, 34011)
UNSTAGED = 10100               # Sickly Exile Rion: in no pool or expert lineup


def save_file(path: Path):
    out = sqlite3.connect(path)
    for name, t in json.loads((FIX / "saves" / f"{IPAD}.json").read_text()).items():
        out.execute(t["sql"])
        if t["rows"]:
            cols = list(t["rows"][0])
            out.executemany(f"insert into {name} ({','.join(cols)}) values ({','.join('?' * len(cols))})",
                            [tuple(r[c] for c in cols) for r in t["rows"]])
    out.commit()
    out.close()


@needs_stage
class SessionTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(dir=BUILD)
        root = Path(self.dir.name)
        self.save = root / "game.db"
        save_file(self.save)
        stage_path = root / "deckbuilder" / "stage.db"
        stage_invoke = cli_invoke(stage_path)
        self.opponent = {"id": 9000000123, "name": "Pod 042", "points": 4812, "costumes": [UNSTAGED, 35036, 33029], "weapons": [0, 0, 0]}

        def shim(payload):
            if payload.get("target") == "deckbuilder_stage":
                return stage_invoke(payload)
            if payload["action"] == "arena_matching":
                return {"ok": True, "data": [self.opponent]}
            raise AssertionError(payload["action"])
        small_pool = lambda tables, experts, **kw: [35036, 33029, 31032, 32035, 34048, 32028, 34010, 34012]
        patches = [mock.patch.object(config, "GAME_DB_PATH", self.save, create=True),
                   mock.patch.object(config, "MASTERDATA_DIR", MASTER, create=True),
                   mock.patch.object(config, "NAMES_DIR", NAMES, create=True),
                   mock.patch.object(config, "find_master_data_bin", lambda: MASTER_BIN, create=True),
                   mock.patch.object(db, "_shim", shim),
                   mock.patch.object(generate, "default_pool", small_pool),
                   mock.patch.object(db, "ARENA_TABLE_SIZE", 6),
                   mock.patch.dict(db._sessions, clear=True)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.dir.cleanup)

    def in_thread(self, fn):
        out = {}
        def run():
            try:
                out["value"] = fn()
            except BaseException as exc:   # noqa: BLE001 — carried back to the test
                out["error"] = exc
        t = threading.Thread(target=run)
        t.start()
        t.join()
        if "error" in out:
            raise out["error"]
        return out.get("value")

    def test_reading_never_builds_the_stage(self):
        """Building it loads master data the running server reads: only
        POST /decks/prepare does (the game guard pauses the server for it)."""
        with self.assertRaises(db.StageNotReady):
            db.session(1)
        db.prepare(1)
        self.assertTrue(db.session(1).page(db.criteria_from(db.session(1), {}), 0, 1).items)

    def test_a_session_works_from_any_thread(self):
        db.prepare(1)
        s = self.in_thread(lambda: db.session(1))
        page = s.page(db.criteria_from(s, {}), 0, 3)        # on this thread
        self.assertTrue(page.items)
        self.in_thread(lambda: s.page(db.criteria_from(s, {}), 3, 3))

    def test_tiles_and_detail_name_each_costume(self):
        db.prepare(1)
        s = db.session(1)
        r = s.page(db.criteria_from(s, {}), 0, 1).items[0]
        self.assertEqual([t["id"] for t in s.tiles(r)], list(r.lineup))
        self.assertEqual([c["costume_id"] for c in s.detail(r)["characters"]], list(r.lineup))

    def test_refresh_writes_the_arena_files(self):
        db.prepare(1)
        db.session(1)
        self.in_thread(lambda: db._refresh_arena_now(1))
        decks, players = db._arena_files()
        self.assertTrue(json.loads(decks.read_text())["decks"])
        self.assertIn("1", json.loads(players.read_text()))

    def test_against_an_opponent_outside_the_stage(self):
        """An opponent whose costumes the stage lacks is staged when asked for. (With the baked data shipped the stage
        holds every playable costume, so this is the case without it.)"""
        from unittest import mock
        patch = mock.patch.object(db, "_baked", lambda: None)
        patch.start(); self.addCleanup(patch.stop)
        db.prepare(1)
        s = db.session(1)
        with self.assertRaises(db.StageNotReady) as caught:
            s.against(str(self.opponent["id"]))
        self.assertIn(UNSTAGED, caught.exception.extra)
        db.prepare(1, against=str(self.opponent["id"]))
        s = db.session(1)
        deck = s.against(str(self.opponent["id"]))
        self.assertIsNotNone(deck)
        self.assertIn(UNSTAGED, [c.costume.id for c in deck.characters() if c])
        page = s.page(db.criteria_from(s, {"against": str(self.opponent["id"])}), 0, 3)
        self.assertTrue(page.items)

    def test_the_baked_results_are_used_when_the_fighters_match(self):
        """Prepared with the shipped baked data: the stage holds every baked piece, its fighters match the bake's
        fingerprint, and All maxed against the general meta answers from the baked lists."""
        if db._baked() is None:
            self.skipTest("no baked data shipped")
        db.prepare(1)
        marker = json.loads((Path(config.GAME_DB_PATH).parent / "deckbuilder" / "stage.json").read_text())
        self.assertTrue(marker["baked_ok"], marker.get("baked_here"))
        s = db.session(1)
        c = db.criteria_from(s, {"mode": "best"})
        self.assertTrue(s.gen.baked_applies(c))
        page = s.page(c, 0, 3)
        self.assertEqual([r.lineup for r in page.items], [r.lineup for r in db._baked().records("attack")[:3]])

    def test_stage_rebuilt_when_the_shipped_data_changes(self):
        db.prepare(1)
        marker = Path(config.GAME_DB_PATH).parent / "deckbuilder" / "stage.json"
        m = json.loads(marker.read_text())
        self.assertIn("data", m)
        built = (marker.parent / "stage.db").stat().st_mtime_ns
        m["data"] = "an older experts.json"
        marker.write_text(json.dumps(m))
        db._sessions.clear()
        with self.assertRaises(db.StageNotReady):
            db.session(1)
        db.prepare(1)
        self.assertNotEqual((marker.parent / "stage.db").stat().st_mtime_ns, built)

    def test_a_deck_with_a_missing_costume(self):
        con = sqlite3.connect(self.save)
        con.execute("delete from user_costumes where costume_id=34012")
        con.commit()
        con.close()
        db.prepare(1)
        s = db.session(1)
        from deckbuilder import power
        r = power.deck_power(model.Deck(s.base, 1, 1), s.tables)
        self.assertEqual(len(r.characters), 3)
        self.assertEqual([c.total for c in r.characters].count(0), 1)
        quest = model.Deck(s.base, 1, 1)
        self.assertIn("missing", model.deck_summary(quest, s.tables))


if __name__ == "__main__":
    unittest.main()
