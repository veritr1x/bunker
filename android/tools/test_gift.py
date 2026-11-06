#!/usr/bin/env python3
"""Pod Programs › Gift (android_gift.py): the catalog by purpose, sending and
the waiting gifts. Needs the Android Python requirements."""
from pathlib import Path
import json, sys, tempfile, unittest
from unittest import mock

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
from web import config  # noqa: E402
import android_gift as gift  # noqa: E402

DAY = 86_400_000
NOW = 1_700_000_000_000


def rec(i, name, **kw):
    return dict({"id": i, "name": name, "name_found": True}, **kw)


NAMES = {
    "consumables": [rec(1, "Gold", ConsumableItemType=100, ConsumableItemTermId=0),
                    rec(1002, "Premium Summon Ticket", ConsumableItemType=200, ConsumableItemTermId=0),
                    rec(3007, "Event Small Stamina Boost", ConsumableItemType=300, ConsumableItemTermId=1),
                    rec(3008, "Event Small Stamina Boost", ConsumableItemType=300, ConsumableItemTermId=2),
                    rec(3009, "Event Small Stamina Boost", ConsumableItemType=300, ConsumableItemTermId=3),
                    rec(8501, "Shard (Weekly Summons A)", ConsumableItemType=120, ConsumableItemTermId=0),
                    rec(8546, "Shard (Weekly Summons A)", ConsumableItemType=120, ConsumableItemTermId=0),
                    rec(9, "Hidden", ConsumableItemType=200, ConsumableItemTermId=0, name_found=False)],
    "materials": [rec(100001, "Small Character Enhancement", MaterialType=20, RarityType=10),
                  rec(311003, "Advanced Handbook", MaterialType=90, RarityType=40),
                  rec(200001, "Small Weapon Enhancement", MaterialType=10, RarityType=10),
                  rec(500001, "Small Fish", MaterialType=30, RarityType=10)],
    "playable_costumes": [rec(10100, "Sickly Exile", character_name="Rion", RarityType=20)],
    "weapons": [rec(101011, "Solitary Pistol", RarityType=20, AttributeType=2),
                rec(101012, "Solitary Pistol", RarityType=20, AttributeType=5),
                rec(9018011, "Solitary Pistol", RarityType=10, AttributeType=2),
                rec(102011, "Iron Blade", RarityType=30, AttributeType=1)],
    "companions": [rec(1, "Bear: Indy"), rec(99, "Test Bear")],
    "parts": [rec(1, "Solemnity", RarityType=10, PartsGroupId=1), rec(2, "Solemnity", RarityType=10, PartsGroupId=1),
              rec(6, "Solemnity", RarityType=20, PartsGroupId=1), rec(7, "Stray", RarityType=10, PartsGroupId=9)],
    "thoughts": [rec(10100834, "Debris: Vigor Chunk", RarityType=40), rec(20100831, "Debris: Vigor Chunk", RarityType=40),
                 rec(30000001, "Debris: Aegis", RarityType=30)],
}
TABLES = {
    "ConsumableItemTerm": [{"ConsumableItemTermId": 1, "StartDatetime": NOW - 40 * DAY, "EndDatetime": NOW - 30 * DAY},
                           {"ConsumableItemTermId": 2, "StartDatetime": NOW - DAY, "EndDatetime": NOW + DAY},
                           {"ConsumableItemTermId": 3, "StartDatetime": NOW + 400 * DAY, "EndDatetime": NOW + 500 * DAY}],
    "CatalogWeapon": [{"WeaponId": 101011}, {"WeaponId": 101012}, {"WeaponId": 102011}],
    "CatalogPartsGroup": [{"PartsGroupId": 1}],
    "CatalogThought": [{"ThoughtId": 10100834}, {"ThoughtId": 20100831}, {"ThoughtId": 30000001}],
    "CatalogCompanion": [{"CompanionId": 1}],
}


class GameData(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        names, master = self.dir / "names", self.dir / "masterdata"
        names.mkdir(), master.mkdir()
        for kind, records in NAMES.items():
            (names / f"{kind}.json").write_text(json.dumps({"records": records}))
        for table, rows in TABLES.items():
            (master / f"EntityM{table}Table.json").write_text(json.dumps(rows))
        for p in (mock.patch.object(config, "NAMES_DIR", names, create=True),
                  mock.patch.object(config, "MASTERDATA_DIR", master, create=True)):
            p.start()
            self.addCleanup(p.stop)

    def group(self, card, name, now=NOW):
        cards = {c.name: c for c in gift.catalog(now)}
        return {g.name: g for g in cards[card].groups}[name].entries


class Catalog(GameData):
    def test_six_cards_in_order(self):
        self.assertEqual([c.name for c in gift.catalog(NOW)],
                         ["Currency", "Summoning", "Character growth", "Weapon growth", "Collection", "Everyday"])

    def test_no_row_repeats(self):
        for card in gift.catalog(NOW):
            for g in card.groups:
                rows = [(e.name, e.stars) for e in g.entries]  # a memoir set is listed once per rarity
                self.assertEqual(len(rows), len(set(rows)), (card.name, g.name, rows))

    def test_only_named_things(self):
        self.assertNotIn("Hidden", [e.name for e in self.group("Summoning", "Summon tickets")])

    def test_gems_and_gold(self):
        got = [(e.name, e.possession_type, e.possession_id) for e in self.group("Currency", "Gems & gold")]
        self.assertEqual(got, [("Gems", 12, 0), ("Paid Gems", 11, 0), ("Gold", 6, 1)])

    def test_event_copy_is_the_one_usable_now(self):
        (stamina,) = self.group("Everyday", "Stamina")
        self.assertEqual(stamina.possession_id, 3008)

    def test_event_copy_falls_back_to_latest(self):
        (stamina,) = self.group("Everyday", "Stamina", now=NOW + 600 * DAY)
        self.assertEqual(stamina.possession_id, 3009)

    def test_weapons_only_from_the_collection(self):
        names = sorted(e.name for e in self.group("Collection", "Weapons"))
        self.assertEqual(names, ["Iron Blade", "Solitary Pistol (Fire)", "Solitary Pistol (Water)"])

    def test_memoirs_one_per_set_and_rarity(self):
        memoirs = self.group("Collection", "Memoirs")
        self.assertEqual(sorted((e.name, e.stars) for e in memoirs), [("Solemnity", 1), ("Solemnity", 2)])

    def test_same_named_debris_are_numbered(self):
        names = sorted(e.name for e in self.group("Collection", "Debris"))
        self.assertEqual(names, ["Debris: Aegis", "Debris: Vigor Chunk · 1", "Debris: Vigor Chunk · 2"])

    def test_one_per_gift_kinds(self):
        for card, group in (("Collection", "Characters"), ("Collection", "Companions"), ("Collection", "Debris")):
            self.assertTrue(all(e.one_per_gift for e in self.group(card, group)), group)
        self.assertFalse(any(e.one_per_gift for e in self.group("Character growth", "Enhancement")))
        self.assertEqual([e.name for e in self.group("Collection", "Characters")], ["Rion (Sickly Exile)"])
        self.assertEqual([e.name for e in self.group("Collection", "Companions")], ["Bear: Indy"])


GIFTS_SCHEMA = """CREATE TABLE user_gifts (user_id INTEGER NOT NULL, user_gift_uuid TEXT NOT NULL, is_received INTEGER NOT NULL DEFAULT 0,
    possession_type INTEGER NOT NULL DEFAULT 0, possession_id INTEGER NOT NULL DEFAULT 0, count INTEGER NOT NULL DEFAULT 0,
    grant_datetime INTEGER NOT NULL DEFAULT 0, description_gift_text_id INTEGER NOT NULL DEFAULT 0, equipment_data BLOB,
    expiration_datetime INTEGER, received_datetime INTEGER, PRIMARY KEY (user_id, user_gift_uuid))"""


class Sending(GameData):
    def setUp(self):
        super().setUp()
        import sqlite3
        self.db = self.dir / "game.db"
        with sqlite3.connect(self.db) as db:
            db.execute(GIFTS_SCHEMA)
            rows = [(1, "a", 0, 5, 100001, 3, NOW, 90000, None), (1, "b", 1, 5, 100001, 9, NOW, 90000, None),
                    (1, "c", 0, 6, 1002, 1, NOW - 1, 1, None), (1, "d", 0, 6, 1002, 1, NOW, 1, NOW - DAY),
                    (2, "e", 0, 5, 100001, 4, NOW, 90000, None)]
            db.executemany("INSERT INTO user_gifts (user_id, user_gift_uuid, is_received, possession_type, possession_id, count,"
                           " grant_datetime, description_gift_text_id, expiration_datetime) VALUES (?,?,?,?,?,?,?,?,?)", rows)
        (self.dir / "masterdata" / "EntityMGiftTextTable.json").write_text(json.dumps([{"GiftTextId": 90000, "LanguageType": 2, "Text": "x"}]))
        self.calls = []
        def shim(payload, **_):
            self.calls.append(payload)
            return {"ok": True, "applied": 7 if payload["action"] == "gift_room" else payload["count"]}
        self.backups = []
        for p in (mock.patch.object(config, "GAME_DB_PATH", self.db, create=True),
                  mock.patch.object(gift, "_shim", shim),
                  mock.patch.object(gift, "_backup", lambda: self.backups.append(1)),
                  mock.patch.object(gift, "_master", lambda: "/master.bin.e")):
            p.start()
            self.addCleanup(p.stop)

    def test_waiting_lists_only_bunker_gifts(self):
        waiting = gift.waiting(1)
        self.assertEqual([(w["possession_type"], w["possession_id"], w["count"]) for w in waiting], [(5, 100001, 3)])
        self.assertEqual(waiting[0]["name"], "Small Character Enhancement")
        self.assertEqual(gift.waiting_count(1, now_ms=NOW), 2)  # every unclaimed, unexpired gift

    def test_send_passes_the_request_to_the_shim(self):
        gift.send(1, 5, 100001, 3)
        self.assertEqual(self.calls, [{"action": "send_gift", "db_path": str(self.db), "master_data_path": "/master.bin.e",
                                       "user_id": 1, "possession_type": 5, "possession_id": 100001, "count": 3}])
        self.assertEqual(self.backups, [1])

    def test_room_comes_from_the_shim(self):
        self.assertEqual(gift.room(1, 5, 100001), 7)
        self.assertEqual(self.calls[0]["action"], "gift_room")
        self.assertEqual(self.backups, [])  # reading only

    def test_without_gift_text_nothing_is_sent(self):
        (self.dir / "masterdata" / "EntityMGiftTextTable.json").write_text(json.dumps([{"GiftTextId": 1, "LanguageType": 2, "Text": "x"}]))
        self.assertFalse(gift.has_gift_text())
        with self.assertRaises(gift.GiftError):
            gift.send(1, 5, 100001, 3)
        self.assertEqual(self.calls, [])

    def test_routes(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(gift.router)
        c = TestClient(app)
        r = c.post("/gift/send", json={"user": 1, "possession_type": 5, "possession_id": 100001, "count": 3})
        self.assertEqual((r.status_code, r.json()), (200, {"ok": True}))
        self.assertEqual(r.headers.get("x-bunker-keep-playing"), "1")
        self.assertEqual(c.get("/gift/room", params={"user": 1, "type": 5, "id": 100001}).json(), {"room": 7})
        self.assertEqual(c.get("/gift/waiting-count", params={"user": 1}).json()["count"], 2)
        half = c.post("/gift/send", json={"user": 1, "possession_type": 5, "possession_id": 100001, "count": 2.5})
        self.assertEqual(half.status_code, 400)  # not cut down to 2
        bad = c.post("/gift/send", json={"user": 1, "possession_type": 5, "possession_id": 100001})
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(bad.json()["ok"])


INTRO = ("Send yourself anything the game can hold. You claim it in the game's Gift Box like any other gift. "
         "The game keeps running: the Gift Box shows it after your next action.")


class Page(Sending):
    def page(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(gift.router)
        with mock.patch.object(gift, "game_now", lambda: NOW):
            return TestClient(app).get("/gift", params={"user": 1}).text

    def test_page_has_the_six_cards_and_the_intro(self):
        page = self.page()
        self.assertIn(INTRO, page)
        positions = [page.index(f'data-card="{name}"') for name in
                     ("Currency", "Summoning", "Character growth", "Weapon growth", "Collection", "Everyday")]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('class="giftbox"', page)  # no in-game preview
        self.assertIn("Small Character Enhancement ×3", page)  # waiting in the Gift Box
        self.assertIn('id="send"', page)

    def test_owned_and_waiting_debris_are_marked(self):
        import sqlite3
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO user_gifts (user_id, user_gift_uuid, is_received, possession_type, possession_id, count,"
                       " grant_datetime, description_gift_text_id) VALUES (1, 'w', 0, 14, 20100831, 1, 1, 90000)")
        with mock.patch.object(gift, "_owned_debris", lambda user: {30000001}):
            cards = gift.page_cards(1)
        debris = {e["possession_id"]: e for e in [g for g in [c for c in cards if c["name"] == "Collection"][0]["groups"]
                                                   if g["name"] == "Debris"][0]["entries"]}
        self.assertEqual(debris[30000001]["blocked"], "Owned")
        self.assertEqual(debris[20100831]["blocked"], "In Gift Box")
        self.assertEqual(debris[10100834]["blocked"], "")

    def test_the_page_refuses_rather_than_trims(self):
        page = self.page()
        self.assertNotIn("Math.min(", page)  # a count above the room is refused, not cut down
        self.assertIn("more than can be claimed", page)
        self.assertIn("const sending = chosen", page)  # the item named after a send is the one sent

    def test_without_gift_text_the_page_says_so(self):
        (self.dir / "masterdata" / "EntityMGiftTextTable.json").write_text("[]")
        page = self.page()
        self.assertIn("Apply a content preset", page)
        self.assertNotIn('id="send"', page)

    def test_nav_and_editors_link_to_gift(self):
        templates = root / "overlays/python/web/templates"
        self.assertIn('href="/gift"', (templates / "base.html").read_text())
        for name in ("user_items.html", "user_costumes.html", "user_weapons.html"):
            self.assertIn("/gift/waiting-count", (templates / name).read_text(), name)


if __name__ == "__main__":
    unittest.main()
