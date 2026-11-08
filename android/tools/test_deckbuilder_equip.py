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
        self.assertEqual(mains, [12, 12, 28])      # ATK %, ATK %, crit rate (the second memoir's)
        _, actors, _ = power.actors_for(eq.deck, tables())
        self.assertGreaterEqual(power.character_stats(actors[0], tables())["crit"], 500)

    def test_attacker_memoirs_stack_crit_like_the_game(self):
        """The attacker set at its fullest and legal: ATK% / crit rate / ATK% mains (only the second memoir may main
        crit), crit rate 20% main + two 25% sub stats (their top), crit damage 36% + 12% + 12% sub stats (the game's
        limits; NieR Re[in] Guide). Sarafa reaches 80% crit rate (52.5% with one roll per sub stat)."""
        eq = equip.equip((SARAFA, RION, SARYU), equip.Mode("best"), self.stage, self.stage, tables(), self.experts)
        subs = [(r["status_kind_type"], r["status_change_value"])
                for m in eq.specs[0].memoirs
                for r in eq.deck.save.q("select * from user_parts_status_subs where user_id=? and user_parts_uuid=?", m.uuid)]
        crit_rate = sum(v for k, v in subs if k == 4)
        crit_damage = sum(v for k, v in subs if k == 3)
        self.assertEqual(crit_rate, 500)
        self.assertEqual(crit_damage, 600)
        _, actors, _ = power.actors_for(eq.deck, tables())
        self.assertEqual(power.character_stats(actors[0], tables())["crit"], 800)

    def test_main_weapon_sets_element(self):
        eq = equip.equip((SARAFA, RION, SARYU), equip.Mode("best"), self.stage, self.stage, tables(), self.experts,
                         elements=("light", None, None))
        w = eq.deck.characters()[0].main_weapon
        self.assertEqual(tables().idx("Weapon", "WeaponId")[w.id]["AttributeType"], 3)
        self.assertEqual(eq.reasons[(SARAFA, "main_weapon")],
                         "Top-ranked Light weapon for this costume's weapon type. Light: +20% damage to Dark.")

    def test_a_fighter_carries_its_subs_memoir_set_and_debris(self):
        """As the client collects them (power.Actor): both sub weapons' abilities, the memoir set bonus that is
        active, and the debris, besides the costume's and the main weapon's."""
        from deckbuilder.sim import units
        eq = equip.equip((SARAFA, RION, SARYU), equip.Mode("best"), self.stage, self.stage, tables(), self.experts)
        _, actors, _ = power.actors_for(eq.deck, tables())
        a = actors[0]
        got = units.gear_abilities(a)
        want = [(x.ability_id, x.level) for w in (a.sub1, a.sub2) if w for x in w["abilities"] if not x.locked]
        want += [(x.ability_id, x.level) for x in a.series_bonus if not x.locked]
        want += [(a.thought.ability_id, a.thought.level)] if a.thought else []
        self.assertEqual(got, want)
        self.assertTrue(a.thought and a.series_bonus and a.sub1)
        bare = units.build_unit(a.costume["id"], "dark", power.character_stats(a, tables()), a.main["id"])
        full = units.build_unit(a.costume["id"], "dark", power.character_stats(a, tables()), a.main["id"], extra_abilities=got)
        self.assertGreaterEqual(len(full["passives"]), len(bare["passives"]))
        self.assertNotEqual((full["passives"], full["mods"]), (bare["passives"], bare["mods"]))


class MainWeaponReasonTest(unittest.TestCase):
    """The ⓘ note on a main weapon: where it came from, then the element it gives (from the weapon itself)."""
    def test_ranked(self):
        self.assertEqual(equip.main_weapon_reason("ranked", "fire", owned=False),
                         "Top-ranked Fire weapon for this costume's weapon type. Fire: +20% damage to Wind, −20% to Water.")

    def test_ranked_and_owned(self):
        self.assertEqual(equip.main_weapon_reason("ranked", "water", owned=True),
                         "Top-ranked Water weapon for this costume's weapon type; you own it. Water: +20% damage to Fire, −20% to Wind.")

    def test_experts_choice(self):
        self.assertEqual(equip.main_weapon_reason("expert", "dark", owned=False),
                         "The experts' choice for this costume. Dark: +20% damage to Light.")

    def test_baked_picks(self):
        """Baked decks say what the bake picked the weapon for: fights, or Force (Sort: Force)."""
        self.assertEqual(equip.main_weapon_reason("fights", "fire", owned=False),
                         "Picked because this costume won the most simulated fights with it. Fire: +20% damage to Wind, −20% to Water.")
        self.assertEqual(equip.main_weapon_reason("force", "light", owned=False),
                         "Picked because it gives this costume the most Force. Light: +20% damage to Dark.")

    def test_your_own_instead_of_adding_one(self):
        self.assertEqual(equip.main_weapon_reason("yours", "wind", owned=True),
                         "Your best weapon of this costume's weapon type, used instead of adding one. Wind: +20% damage to Water, −20% to Fire.")


if __name__ == "__main__":
    unittest.main()
