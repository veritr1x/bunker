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
        # the 15 Arena decks, then the 15 Loadout (quest) decks
        self.assertEqual([(s.deck_type, s.number) for s in slots], [(2, n) for n in range(1, 16)] + [(1, n) for n in range(1, 16)])
        first = slots[0]
        self.assertEqual((first.deck_type, first.label), (2, "Arena deck 1 (defense)"))
        self.assertIn("Lars", first.summary)
        self.assertIsNone(slots[5].summary)
        self.assertEqual(slots[15].label, "Loadout deck 1")


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


    def low_spec(self, base):
        return model.CharacterSpec(costume=model.PieceRef("costume", base.pick("costume", costume_id=LOW), "save"),
                                   main_weapon=None, subs=[], companion=None, memoirs=[], debris=None)

    def slab(self, save, cid):
        return save.one("select coalesce(sum(level), 0) n from user_character_board_abilities where user_id=? and character_id=?", cid)["n"]

    def test_raises_list_the_mythic_slab(self):
        """Raising a costume also gives its character the staged Mythic Slab: the list says so."""
        base = model.Save(snapshot_con(IPAD), 1)
        cid = tables().idx("Costume", "CostumeId")[LOW]["CharacterId"]
        raises = model.raises_needed([self.low_spec(base)], base, self.stage, model.Inventory(base, tables()))
        slab = [(r.current, r.target) for r in raises if r.field == "mythic_slab"]
        self.assertEqual(slab, [(self.slab(base, cid), self.slab(self.stage, cid))])
        self.assertLess(slab[0][0], slab[0][1])

    def test_a_staged_costume_the_player_owns_can_be_raised(self):
        """All maxed builds from staged costumes; one the player owns is written as theirs, so it is theirs to raise."""
        base = model.Save(snapshot_con(IPAD), 1)
        staged = model.CharacterSpec(costume=model.PieceRef("costume", self.stage.pick("costume", costume_id=LOW), "stage"),
                                     main_weapon=None, subs=[], companion=None, memoirs=[], debris=None)
        raises = model.raises_needed([staged], base, self.stage, model.Inventory(base, tables()))
        self.assertIn((LOW, "level", 61, 100), [(r.costume_id, r.field, r.current, r.target) for r in raises])

    def test_raise_gives_the_slab_and_keeps_the_players_rank(self):
        base = model.Save(snapshot_con(IPAD), 1)
        cid = tables().idx("Costume", "CostumeId")[LOW]["CharacterId"]
        base.db.execute("update user_characters set level=4 where character_id=?", (cid,))   # above the stage's rank 1
        raised = model.compose(base, self.stage, [self.low_spec(base)], 2, 9, tables(), raises=[LOW])
        rank = lambda s: s.one("select level from user_characters where user_id=? and character_id=?", cid)["level"]
        self.assertEqual(rank(raised.save), rank(base))           # as the write does: the rank stays the player's
        self.assertEqual(self.slab(raised.save, cid), self.slab(self.stage, cid))

    def test_raise_all_raises_every_owned_costume_of_the_deck(self):
        """All maxed: the player's own costumes and characters count fully raised (and are raised on write)."""
        base = model.Save(snapshot_con(IPAD), 1)
        spec = self.low_spec(base)
        a = model.compose(base, self.stage, [spec], 2, 9, tables(), raise_all=True)
        b = model.compose(base, self.stage, [spec], 2, 9, tables(), raises=[LOW])
        self.assertEqual(power.deck_power(a, tables()).total, power.deck_power(b, tables()).total)
        self.assertEqual(model.owned_costumes([spec], base), [LOW])

    def test_all_maxed_counts_the_players_costumes_raised(self):
        from deckbuilder import equip, experts
        base = model.Save(snapshot_con(IPAD), 1)
        lv = lambda d: d.save.one("select level from user_costumes where user_id=? and costume_id=?", LOW)["level"]
        best = equip.equip((LOW,), equip.Mode("best"), base, self.stage, tables(), experts.Experts.load(tables()))
        owned = equip.equip((LOW,), equip.Mode("owned", 2), base, self.stage, tables(), experts.Experts.load(tables()))
        self.assertEqual((lv(best.deck), lv(owned.deck)), (100, 61))   # What I own: as it is unless ticked


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
