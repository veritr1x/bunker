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


if __name__ == "__main__":
    unittest.main()
