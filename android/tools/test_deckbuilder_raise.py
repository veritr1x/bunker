#!/usr/bin/env python3
"""Deck Builder: fully raised pieces (built by the server's own Upgrade Manager
actions on a staging save, deckbuilder/stage.py) and theoretical-best memoirs
(deckbuilder/raise_.py)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, cli_invoke, needs_master, needs_stage, tables
from deckbuilder import raise_, stage

SARAFA, RION, SARYU = 35036, 33029, 34048
STEPHANOS, STEPHANOS_IV = 440001, 440031
BLADE_OF_PARTING_IV = 430031


@needs_master
class MemoirTest(unittest.TestCase):
    def test_memoir_main_values_at_15(self):
        t = tables()
        v = lambda kind, calc: raise_.memoir_main_value(raise_.main_status_id(kind, calc, t), 15, t)
        # The design's 610 / 19.5% / 6,600 were Bunker-server figures; the
        # client computes from the master data's numerical functions (the same
        # path the exact Force check confirms on real memoirs), which give:
        self.assertEqual(v(2, 1), 600)    # ATK flat
        self.assertEqual(v(7, 1), 600)    # DEF flat
        self.assertEqual(v(2, 2), 200)    # ATK 20%
        self.assertEqual(v(7, 2), 200)    # DEF 20%
        self.assertEqual(v(6, 2), 200)    # HP 20%
        self.assertEqual(v(6, 1), 6900)   # HP flat
        # Original game rules (not rolled by Bunker's server): crit rate 20%,
        # crit damage 25%, agility 120 (wiki). The master data's numerical
        # functions decide; these are what they give at +15.
        self.assertEqual(v(4, 1), 200)    # crit rate 20%
        self.assertEqual(v(3, 1), 250)    # crit damage 25%
        self.assertEqual(v(1, 1), 120)    # agility 120

    def test_main_status_is_the_top_rarity_row(self):
        t = tables()
        self.assertEqual(raise_.main_status_id(4, 1, t), 28)
        self.assertEqual(raise_.main_status_id(2, 1, t), 4)
        self.assertEqual(raise_.main_status_id(1, 1, t), 36)

    def test_memoir_subs_level12_step(self):
        t = tables()
        parts_id = raise_.top_parts_id(raise_.parts_group_of_set(17, t)[0], t)
        spec = raise_.memoir_spec(parts_id, "crit_rate", ["crit_damage", "attack_pct", "attack_pct", "agility"], t)
        self.assertEqual(spec["parts_status_main_id"], 28)
        self.assertEqual(spec["level"], 15)
        subs = {s["slot"]: (s["kind_type"], s["calc_type"], s["value"]) for s in spec["subs"]}
        self.assertEqual(subs, {1: (3, 1, 140), 2: (2, 2, 75), 3: (2, 2, 75), 4: (1, 1, 75)})
        with self.assertRaises(ValueError):
            raise_.memoir_spec(parts_id, "attack", ["hp_pct"] * 5, t)
        with self.assertRaises(ValueError):
            raise_.memoir_spec(parts_id, "evasion", [], t)


@needs_stage
class StageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        cls.path = Path(cls.dir.name) / "stage.db"
        st = stage.Stager(cli_invoke(cls.path), tables())
        t = tables()
        memoir = raise_.memoir_spec(raise_.top_parts_id(raise_.parts_group_of_set(17, t)[0], t), "crit_rate",
                                    ["crit_damage", "attack_pct", "attack_pct", "attack_pct"], t)
        st.build(costume_ids=[SARAFA, RION, SARYU], weapon_ids=[STEPHANOS, 430001], companion_ids=[1], thought_ids=[],
                 memoirs=[memoir])
        cls.db = sqlite3.connect(f"file:{cls.path}?mode=ro", uri=True)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.dir.cleanup()

    def q(self, sql, *a):
        return self.db.execute(sql, a).fetchall()

    def test_raised_costume_is_level_100_max_awakening_full_board(self):
        level, lb, awaken, slots = self.q("select level, limit_break_count, awaken_count, costume_lottery_effect_unlocked_slot_count"
                                          " from user_costumes where costume_id=?", SARAFA)[0]
        self.assertEqual((level, lb, awaken, slots), (100, 4, 5, 3))
        character = tables().idx("Costume", "CostumeId")[SARAFA]["CharacterId"]
        self.assertEqual(self.q("select rebirth_count from user_character_rebirths where character_id=?", character), [(5,)])
        self.assertTrue(self.q("select 1 from user_character_board_status_ups where character_id=?", character))
        karma = self.q("select count(*) from user_costume_lottery_effects e join user_costumes c using (user_costume_uuid)"
                       " where c.costume_id=? and e.odds_number > 0", SARAFA)[0][0]
        self.assertEqual(karma, 3)

    def test_raised_weapon_ex_is_iv_form(self):
        ids = {r[0] for r in self.q("select weapon_id from user_weapons")}
        self.assertIn(STEPHANOS_IV, ids)
        self.assertIn(BLADE_OF_PARTING_IV, ids)
        self.assertNotIn(STEPHANOS, ids)
        lb, = self.q("select limit_break_count from user_weapons where weapon_id=?", STEPHANOS_IV)[0]
        self.assertEqual(lb, 4)
        skills = self.q("select s.level from user_weapon_skills s join user_weapons w using (user_weapon_uuid) where w.weapon_id=?", STEPHANOS_IV)
        self.assertTrue(skills and all(l == 15 for (l,) in skills), skills)

    def test_raised_companion_is_level_50(self):
        self.assertEqual(self.q("select level from user_companions where companion_id=1"), [(50,)])

    def test_memoir_written_with_crit_main(self):
        rows = self.q("select p.level, p.parts_status_main_id, count(s.status_index) from user_parts p"
                      " join user_parts_status_subs s using (user_parts_uuid) group by p.user_parts_uuid")
        self.assertEqual(rows, [(15, 28, 4)])


if __name__ == "__main__":
    unittest.main()
