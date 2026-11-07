#!/usr/bin/env python3
"""Deck Builder: decks put together from the player's save and the staging
save (deckbuilder/model.py), the way the save writer will put them in."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, FIX, cli_invoke, needs_master, needs_stage, save_decks, tables
from deckbuilder import model, power, stage

SNAP = "2d981f327817"            # the late-game snapshot (decks 215842, 197235, ...)
SARAFA, RION, SARYU = 35036, 33029, 34048
IPAD = "129f58f58f43"            # the iPad snapshot: costumes far below max
LOW = 34012                      # owned there at level 61, in its quest deck 1/1
STEPHANOS = 440001


def snapshot_con(snap=SNAP):
    return model.rows_to_db(json.loads((FIX / "saves" / f"{snap}.json").read_text()))


def deck_specs(base: model.Save, deck_type, number):
    """The CharacterSpecs of a deck already in a save, every piece from that save."""
    return model.Deck(base, deck_type, number).specs()


@needs_master
class ComposeFromSaveTest(unittest.TestCase):
    def test_recomposed_decks_keep_the_games_force(self):
        for name, d, inputs in save_decks():
            if not name.startswith(f"save_") or SNAP not in name:
                continue
            base = model.Save(model.rows_to_db(inputs["tables"]), inputs["user_id"])
            specs = deck_specs(base, inputs["deck_type"], inputs["deck_number"])
            deck = model.compose(base, None, specs, 2, 9, tables())
            self.assertEqual(power.deck_power(deck, tables()).total, d["stored_deck"], name)

    def test_characters_view(self):
        base = model.Save(snapshot_con(), 1)
        chars = model.Deck(base, 1, 1).characters()
        self.assertEqual(len(chars), 3)
        self.assertEqual(chars[0].costume.id, 31029)
        for c in chars:
            self.assertEqual(len(c.subs), 2)
            self.assertTrue(c.main_weapon.id and c.companion.id)
            self.assertEqual(len(c.memoirs), 3)

    def test_key_ignores_slot_uuids_but_not_gear(self):
        base = model.Save(snapshot_con(), 1)
        specs = deck_specs(base, 1, 1)
        a = model.compose(base, None, specs, 2, 9, tables())
        b = model.compose(base, None, specs, 2, 8, tables())
        self.assertEqual(a.key(), b.key())
        swapped = [specs[0]._replace(main_weapon=specs[1].main_weapon)] + specs[1:]
        self.assertNotEqual(model.compose(base, None, swapped, 2, 9, tables()).key(), a.key())

    def test_slots_labels(self):
        con = snapshot_con()
        con.execute("create table user_bunker_ext (user_id integer, data text)")
        con.execute("insert into user_bunker_ext values (1, ?)", (json.dumps({"pvp": {"defenseDeckNumber": 1}}),))
        slots = model.slots(model.Save(con, 1), tables())
        self.assertEqual([s.number for s in slots], list(range(1, 16)))
        first = slots[0]
        self.assertEqual((first.deck_type, first.label), (2, "Arena deck 1 (defense)"))
        self.assertIn("Lars", first.summary)
        self.assertIsNone(slots[5].summary)


@needs_stage
class StageDeckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        stage.Stager(cli_invoke(path), tables()).build(costume_ids=[SARAFA, RION, SARYU, LOW], weapon_ids=[STEPHANOS, 430001, 410001],
                                                       companion_ids=[1, 2, 3])
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def theoretical_specs(self):
        st = self.stage
        def first(kind, **where):
            return model.PieceRef(kind, st.pick(kind, **where), "stage")
        out = []
        for costume, weapon, comp in ((SARAFA, 440031, 1), (RION, 430031, 2), (SARYU, 410031, 3)):
            out.append(model.CharacterSpec(costume=first("costume", costume_id=costume), main_weapon=first("weapon", weapon_id=weapon),
                                           subs=[], companion=first("companion", companion_id=comp), memoirs=[], debris=None))
        return out

    def test_theoretical_deck_force_is_exact_and_stable(self):
        deck = model.compose(self.stage, self.stage, self.theoretical_specs(), 2, 1, tables())
        a = power.deck_power(deck, tables())
        b = power.deck_power(model.compose(self.stage, self.stage, self.theoretical_specs(), 2, 1, tables()), tables())
        self.assertEqual(a.total, b.total)
        self.assertTrue(all(c.total > 20000 for c in a.characters), [c.total for c in a.characters])

    def test_missing_and_raises(self):
        base = model.Save(snapshot_con(IPAD), 1)
        inv = model.Inventory(base, tables())
        new_weapon = model.PieceRef("weapon", self.stage.pick("weapon", weapon_id=440031), "stage")
        spec = model.CharacterSpec(costume=model.PieceRef("costume", base.pick("costume", costume_id=LOW), "save"),
                                   main_weapon=new_weapon, subs=[], companion=None, memoirs=[], debris=None)
        self.assertEqual(model.missing_pieces([spec]), [new_weapon])
        raises = model.raises_needed([spec], base, self.stage, inv)
        self.assertEqual([(r.costume_id, r.field, r.current, r.target) for r in raises if r.field == "level"], [(LOW, "level", 61, 100)])
        self.assertIn((1, 1), [u for r in raises for u in r.used_in])
        self.assertIn((1, 1), inv.decks_using(LOW))

    def test_staged_costume_the_player_owns_uses_theirs(self):
        """Like the write (deck_write): a staged costume the player owns is not
        added; the deck uses the player's own, as it is unless ticked."""
        base = model.Save(snapshot_con(IPAD), 1)
        spec = model.CharacterSpec(costume=model.PieceRef("costume", self.stage.pick("costume", costume_id=LOW), "stage"),
                                   main_weapon=None, subs=[], companion=None, memoirs=[], debris=None)
        deck = model.compose(base, self.stage, [spec], 2, 9, tables())
        c = deck.characters()[0].costume
        self.assertEqual(c.uuid, base.pick("costume", costume_id=LOW))
        self.assertEqual(deck.save.one("select count(*) n from user_costumes where user_id=? and costume_id=?", LOW)["n"], 1)
        self.assertEqual(deck.save.one("select level from user_costumes where user_id=? and costume_id=?", LOW)["level"], 61)

    def test_raise_ticked_costume_changes_only_that_costume(self):
        base = model.Save(snapshot_con(IPAD), 1)
        spec = model.CharacterSpec(costume=model.PieceRef("costume", base.pick("costume", costume_id=LOW), "save"),
                                   main_weapon=model.PieceRef("weapon", self.stage.pick("weapon", weapon_id=440031), "stage"),
                                   subs=[], companion=None, memoirs=[], debris=None)
        plain = model.compose(base, self.stage, [spec], 2, 9, tables())
        raised = model.compose(base, self.stage, [spec], 2, 9, tables(), raises=[LOW])
        lv = lambda d: d.save.one("select level from user_costumes where user_id=? and costume_id=?", LOW)["level"]
        self.assertEqual((lv(plain), lv(raised)), (61, 100))
        uuid = base.pick("costume", costume_id=LOW)
        self.assertEqual(raised.save.one("select user_costume_uuid from user_costumes where user_id=? and costume_id=?", LOW)["user_costume_uuid"], uuid)
        other = lambda d: d.save.one("select level from user_costumes where user_id=? and costume_id=?", 34010)["level"]
        self.assertEqual(other(plain), other(raised))



class SnapshotTest(unittest.TestCase):
    """The game's server writes the save in the same process: Deck Builder keeps an in-memory copy, no open file."""

    def test_snapshot_is_a_copy_in_memory(self):
        import sqlite3, tempfile, os
        path = os.path.join(tempfile.mkdtemp(), "game.db")
        con = sqlite3.connect(path)
        con.execute("pragma journal_mode=wal")
        con.execute("create table t(x)")
        con.execute("insert into t values (1)")
        con.commit()
        snap = model.snapshot(path)
        con.execute("insert into t values (2)")
        con.commit()
        self.assertEqual(snap.execute("select count(*) from t").fetchone()[0], 1)
        self.assertEqual(snap.execute("pragma database_list").fetchone()[2], "")

if __name__ == "__main__":
    unittest.main()
