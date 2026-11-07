#!/usr/bin/env python3
"""Deck Builder: equipping a lineup (deckbuilder/equip.py)."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, FIX, cli_invoke, needs_stage, tables
from deckbuilder import equip, experts, model, power, sim, stage

PHANTASMAL_YUDIL, YULE_MARIE, NY_YUDIL = 34040, 31032, 32035
SARAFA, RION, SARYU = 35036, 33029, 34048
IPAD = "129f58f58f43"
OWNED = (34012, 34010, 34011)


@needs_stage
class EquipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.experts = experts.Experts.load(tables())
        plan = equip.stage_plan([(PHANTASMAL_YUDIL, YULE_MARIE, NY_YUDIL), (SARAFA, RION, SARYU), OWNED], tables(), cls.experts,
                                extra_sets=[7])
        stage.Stager(cli_invoke(path), tables()).build(**plan)
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        sim.use(tables())

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def memoir_set(self, eq, slot):
        sets = {self.stage_or_deck(eq).one("select g.parts_id from user_parts g where user_id=? and user_parts_uuid=?", m.uuid)["parts_id"]
                for m in eq.specs[slot].memoirs}
        groups = {tables().idx("Parts", "PartsId")[p]["PartsGroupId"] for p in sets}
        series = {tables().idx("PartsGroup", "PartsGroupId")[g]["PartsSeriesId"] for g in groups}
        self.assertEqual(len(series), 1)
        return series.pop()

    def stage_or_deck(self, eq):
        return eq.deck.save

    def test_set7_overridden_by_set17_with_reason(self):
        expert = experts.ExpertLineup("note", (PHANTASMAL_YUDIL, YULE_MARIE, NY_YUDIL), {str(PHANTASMAL_YUDIL): {"memoir_set": 7}}, "test")
        def prefer(series):
            return lambda deck: 0.6 if self.memoir_set_of(deck, 0) == series else 0.4
        eq = equip.equip(expert.costumes, equip.Mode("best"), self.stage, self.stage, tables(), self.experts, expert=expert, rate=prefer(17))
        self.assertEqual(self.memoir_set(eq, 0), 17)
        [o] = [o for o in eq.overrides if o.costume_id == PHANTASMAL_YUDIL]
        self.assertEqual((o.slot, o.expert_choice, o.data_choice), ("memoirs", 7, 17))
        self.assertIn("DEF −30%", o.reason)
        self.assertEqual(o.evidence["win_rate"], {"expert": 0.4, "data": 0.6})
        # When the data does not back the change, the expert's set stays.
        eq = equip.equip(expert.costumes, equip.Mode("best"), self.stage, self.stage, tables(), self.experts, expert=expert, rate=prefer(7))
        self.assertEqual(self.memoir_set(eq, 0), 7)
        self.assertFalse([o for o in eq.overrides if o.costume_id == PHANTASMAL_YUDIL])

    def memoir_set_of(self, deck, slot):
        spec = deck.specs()[slot]
        p = deck.save.one("select parts_id from user_parts where user_id=? and user_parts_uuid=?", spec.memoirs[0].uuid)["parts_id"]
        g = tables().idx("Parts", "PartsId")[p]["PartsGroupId"]
        return tables().idx("PartsGroup", "PartsGroupId")[g]["PartsSeriesId"]

    def test_owned_mode_respects_allow_missing(self):
        base = model.Save(model.rows_to_db(json.loads((FIX / "saves" / f"{IPAD}.json").read_text())), 1)
        for n in (0, 2):
            eq = equip.equip(OWNED, equip.Mode("owned", n), base, self.stage, tables(), self.experts)
            self.assertLessEqual(len(eq.to_add), n)
            self.assertTrue(all(s.costume.source == "save" for s in eq.specs))
        self.assertTrue(eq.to_add)    # with 2 allowed, the biggest gains are added

    def test_best_mode_memoir_mains_by_role(self):
        eq = equip.equip((SARAFA, RION, SARYU), equip.Mode("best"), self.stage, self.stage, tables(), self.experts)
        mains = sorted(eq.deck.save.one("select parts_status_main_id m from user_parts where user_id=? and user_parts_uuid=?", m.uuid)["m"]
                       for m in eq.specs[0].memoirs)
        self.assertEqual(mains, [12, 28, 32])      # ATK %, crit rate, crit damage
        _, actors, _ = power.actors_for(eq.deck, tables())
        self.assertGreaterEqual(power.character_stats(actors[0], tables())["crit"], 500)

    def test_main_weapon_sets_element(self):
        eq = equip.equip((SARAFA, RION, SARYU), equip.Mode("best"), self.stage, self.stage, tables(), self.experts,
                         elements=("light", None, None))
        w = eq.deck.characters()[0].main_weapon
        self.assertEqual(tables().idx("Weapon", "WeaponId")[w.id]["AttributeType"], 3)
        self.assertIn((SARAFA, "main_weapon"), eq.reasons)


if __name__ == "__main__":
    unittest.main()
