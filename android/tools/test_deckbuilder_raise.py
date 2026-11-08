#!/usr/bin/env python3
"""Deck Builder: fully raised pieces (built by the server's own Upgrade Manager
actions on a staging save, deckbuilder/stage.py) and all-maxed memoirs
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

    def test_memoir_subs_stack_their_rolls(self):
        """The original game (NieR Re[in] Guide, memoirs): a sub stat starts at up to 2.5% (HP/ATK/DEF), 5% crit rate,
        6% crit damage or 12 agility and is raised at +3, +6, +9, +12 and +15; one sub stat tops out at 12.5% / 25% /
        36% / 72. A name given n times is that sub stat with n rolls: a memoir has 4 sub stats and 9 rolls, up to 6 on
        one, and a sub stat never passes its top."""
        t = tables()
        parts_id = raise_.top_parts_id(raise_.parts_group_of_set(17, t)[0], t)
        spec = raise_.memoir_spec(parts_id, "crit_rate", ["crit_damage"] * 6 + ["attack_pct", "hp_pct", "agility"], t)
        self.assertEqual(spec["level"], 15)
        subs = {s["slot"]: (s["kind_type"], s["calc_type"], s["value"]) for s in spec["subs"]}
        self.assertEqual(subs, {1: (3, 1, 360), 2: (2, 2, 25), 3: (6, 2, 25), 4: (1, 1, 12)})
        spec = raise_.memoir_spec(parts_id, "attack_pct", ["crit_rate"] * 6 + ["agility"] * 3, t)
        subs = {s["slot"]: (s["kind_type"], s["calc_type"], s["value"]) for s in spec["subs"]}
        self.assertEqual(subs, {1: (4, 1, 250), 2: (1, 1, 36)})      # crit rate stops at its top, 25%
        with self.assertRaises(ValueError):          # 10 rolls
            raise_.memoir_spec(parts_id, "crit_rate", ["crit_damage"] * 6 + ["attack_pct"] * 4, t)
        with self.assertRaises(ValueError):          # 7 rolls on one sub stat
            raise_.memoir_spec(parts_id, "crit_rate", ["crit_damage"] * 7, t)
        with self.assertRaises(ValueError):          # 5 sub stats
            raise_.memoir_spec(parts_id, "attack", ["hp_pct", "attack_pct", "defense_pct", "crit_rate", "agility"], t)
        with self.assertRaises(ValueError):
            raise_.memoir_spec(parts_id, "evasion", [], t)

    def test_force_memoirs_carry_the_most_force(self):
        """The Force list's memoirs: flat ATK / DEF mains (649 Force each at +15) and HP% at its top with ATK% and DEF%:
        about twice the Force of the crit-built attacker set (3,525 against 1,956)."""
        from deckbuilder import equip, power
        t = tables()
        def set_force(role):
            _, mains, subs = equip.ROLE_MEMOIRS[role]
            specs = equip.memoir_specs(10, mains, subs, t)
            mems = [{"main": t.idx("PartsStatusMain", "PartsStatusMainId")[s["parts_status_main_id"]], "level": 15,
                     "subs": [(x["kind_type"], x["calc_type"], x["value"]) for x in s["subs"]]} for s in specs]
            return sum(power.parts_power(t, mems))
        self.assertEqual(equip.ROLE_MEMOIRS["force"][1], ("attack", "defense", "attack"))
        self.assertEqual((set_force("force"), set_force("attacker")), (3525, 1956))

    def test_a_main_stat_fits_its_place_in_the_set(self):
        """The original game: the set's first memoir mains ATK, DEF or HP; the second may also main crit rate or crit
        damage; the third may also main agility (NieR Re[in] Guide; gorillawiki; ameblo)."""
        self.assertTrue(raise_.main_allowed("attack_pct", 0) and raise_.main_allowed("hp", 0))
        self.assertFalse(raise_.main_allowed("crit_rate", 0))
        self.assertTrue(raise_.main_allowed("crit_damage", 1))
        self.assertFalse(raise_.main_allowed("agility", 1))
        self.assertTrue(raise_.main_allowed("agility", 2))
        self.assertFalse(raise_.main_allowed("crit_rate", 2))
        from deckbuilder import equip
        for role, (_, mains, _) in equip.ROLE_MEMOIRS.items():
            for i, m in enumerate(mains):
                self.assertTrue(raise_.main_allowed(m, i), f"{role}: {m} on memoir {i + 1}")
        with self.assertRaisesRegex(ValueError, "memoir 1"):
            equip.memoir_specs(10, ("crit_rate", "crit_damage", "attack_pct"), ([],) * 3, tables())

    def test_every_sub_stat_can_reach_the_games_top(self):
        for name, top in {"hp_pct": 125, "attack_pct": 125, "defense_pct": 125, "crit_rate": 250, "crit_damage": 360, "agility": 72}.items():
            self.assertEqual(raise_.sub_value(name, raise_.MAX_ROLLS_PER_SUB), top, name)


@needs_stage
class StageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        cls.path = Path(cls.dir.name) / "stage.db"
        st = stage.Stager(cli_invoke(cls.path), tables())
        t = tables()
        memoir = raise_.memoir_spec(raise_.top_parts_id(raise_.parts_group_of_set(17, t)[0], t), "crit_rate",
                                    ["crit_damage"] * 6 + ["attack_pct", "hp_pct", "agility"], t)
        # Rion's karma: the last top-tier option of each slot (not the first, which every other costume gets)
        le = {x["SlotNumber"]: x["CostumeLotteryEffectOddsGroupId"] for x in t.T("CostumeLotteryEffect") if x["CostumeId"] == RION}
        odds = t.grp("CostumeLotteryEffectOddsGroup", "CostumeLotteryEffectOddsGroupId")
        cls.karma = {s: max(o["OddsNumber"] for o in odds[g] if o["RarityType"] == 40) for s, g in le.items()}
        st.build(costume_ids=[SARAFA, RION, SARYU], weapon_ids=[STEPHANOS, 430001], companion_ids=[1], thought_ids=[],
                 memoirs=[memoir], costume_karma={RION: cls.karma})
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
        self.assertEqual(self.q("select level from user_characters where character_id=?", character), [(10,)])   # rank 10
        # every stained glass (important item type 5): a fully progressed account owns them all
        glass = {i["ImportantItemId"] for i in tables().T("ImportantItem") if i["ImportantItemType"] == 5}
        owned = {i for (i,) in self.q("select important_item_id from user_important_items where count > 0")}
        self.assertEqual(glass - owned, set())
        karma = self.q("select count(*) from user_costume_lottery_effects e join user_costumes c using (user_costume_uuid)"
                       " where c.costume_id=? and e.odds_number > 0", SARAFA)[0][0]
        self.assertEqual(karma, 3)

    def test_a_costume_gets_the_karma_asked_for(self):
        """costume_karma sets a costume's karma slot by slot (the bake's best); the others keep the first top-tier."""
        rows = dict(self.q("select e.slot_number, e.odds_number from user_costume_lottery_effects e join user_costumes c"
                           " using (user_costume_uuid) where c.costume_id=?", RION))
        self.assertEqual(rows, self.karma)
        self.assertNotEqual(set(self.karma.values()), {1})
        self.assertEqual({o for (o,) in self.q("select e.odds_number from user_costume_lottery_effects e join user_costumes c"
                                                " using (user_costume_uuid) where c.costume_id=?", SARAFA)}, {1})

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
