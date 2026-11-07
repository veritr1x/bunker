#!/usr/bin/env python3
"""Deck Builder: Force exactly as the game client computes it
(deckbuilder/power.py, a port of Dark.Calculator.CalculatorPower)."""
import unittest

from deckbuilder_testlib import needs_master, save_decks, tables
from deckbuilder import model, power


class PermilTest(unittest.TestCase):
    def test_permil_truncates_toward_zero(self):
        self.assertEqual(power.permil(436, 81), 35)
        self.assertEqual(power.permil(-436, 81), -35)
        self.assertEqual(power.permil(999, 1), 0)


@needs_master
class PowerTest(unittest.TestCase):
    def test_matches_stored_power_exactly(self):
        decks = save_decks()
        self.assertGreaterEqual(len(decks), 9)
        for name, d, inputs in decks:
            r = power.deck_power(model.Deck.from_inputs(inputs), tables())
            self.assertEqual(r.total, d["stored_deck"], name)
            for got, stored in zip(r.characters, d["stored_characters"]):
                if stored is not None:   # None: the save holds no client value for this slot
                    self.assertEqual(got.total, stored, name)

    def test_parts_add_up(self):
        name, d, inputs = save_decks()[0]
        r = power.deck_power(model.Deck.from_inputs(inputs), tables())
        for c in r.characters:
            self.assertEqual(c.total, c.hp + c.atk + c.vit + c.skill, name)
            self.assertEqual(c.hp, sum(v[0] for v in c.parts.values()))

    def test_only_constants_1_to_23_are_read(self):
        self.assertEqual(sorted(power.constants(tables())), list(range(1, 24)))


class CodeOnlyPathsTest(unittest.TestCase):
    """Paths no save sample exercises: pinned to what the client's code does."""

    def test_attribute_conditions(self):
        # from code only (IsMatchAttributeCondition 0x2A11020), no save sample for 3, 4, 7
        m = power.power_attr_match
        self.assertTrue(m(3, 3))
        self.assertFalse(m(1, 3))
        self.assertFalse(m(3, 4))
        self.assertFalse(m(1, 4))
        self.assertTrue(m(4, 7))
        self.assertFalse(m(3, 7))
        self.assertTrue(m(6, 8))

    def test_min_clamps(self):
        # from code only (CalculatorStatus.cctor 0x2A17A10 kMin*), no save sample
        out = power.clamp_min(power.sv(**{}) | {power.ATK: -5, power.HP: 0, power.VIT: -1, power.CRIT_ATK: 10, power.AGI: -3})
        self.assertEqual((out[power.ATK], out[power.HP], out[power.VIT], out[power.CRIT_ATK], out[power.AGI]), (1, 1, 1, 1000, 0))

    def test_vitality_reference_and_conditions(self):
        # from code only (CalculateStatusReferenceValue 0x2A1267C), no save sample on VitalityPower / cond 3
        class A:
            def __init__(self, uuid, attr, vit):
                self.uuid, self.empty, self.main, self.vit_power, self.atk_power, self.hp_power = uuid, False, {"attr": attr}, vit, 0, 0
        owner, other = A("a", 2, 1000), A("b", 3, 2000)
        orig = power.skill_power_def
        try:
            power.skill_power_def = lambda m, d: {"ref_type": 2, "base": 0, "refs": [(7, 8, 500), (7, 3, 100)]}
            # party: 500‰ of both vitality powers, plus 100‰ of the light (3) one only
            self.assertEqual(power.skill_power(None, owner, [owner, other], 1), 500 + 1000 + 200)
            power.skill_power_def = lambda m, d: {"ref_type": 1, "base": 0, "refs": [(7, 8, 500)]}
            self.assertEqual(power.skill_power(None, owner, [owner, other], 1), 500)
        finally:
            power.skill_power_def = orig


@needs_master
class CodeOnlyMasterPathsTest(unittest.TestCase):
    def test_hp_down_abilities_subtract(self):
        # from code only (StatusDown negates every value, 0x280243C), no save sample
        t = tables()
        down = {r["AbilityBehaviourId"] for r in t.T("AbilityBehaviour") if r["AbilityBehaviourType"] == 5}
        self.assertTrue(down)
        groups = {g["AbilityBehaviourGroupId"] for g in t.T("AbilityBehaviourGroup") if g["AbilityBehaviourId"] in down}
        details = {d["AbilityDetailId"] for d in t.T("AbilityDetail") if d["AbilityBehaviourGroupId"] in groups}
        row = next(r for r in t.T("AbilityLevelGroup") if r["AbilityDetailId"] in details)
        ab = power.Ability(t, row["AbilityLevelGroupId"], row["LevelLowerLimit"] or 1, "test")
        hp = [s["value"][power.HP] for s in ab.statuses]
        self.assertTrue(hp and min(hp) < 0, hp)

    def test_stained_glass_adds_for_its_character(self):
        # from code only (CreateStainedGlassStatusList 0x2A0F218), no save owns a stained glass
        t = tables()
        item = next(it for it in t.T("ImportantItem") if it["ImportantItemType"] == 5)
        glass = t.idx("StainedGlass", "StainedGlassId")[item["ExternalReferenceId"]]
        target = next(r for r in t.grp("StainedGlassStatusUpTargetGroup", "StainedGlassStatusUpTargetGroupId")[glass["StainedGlassStatusUpTargetGroupId"]]
                      if r["StatusUpTargetType"] == 1)
        want = power.sv()
        for r in t.grp("StainedGlassStatusUpGroup", "StainedGlassStatusUpGroupId")[glass["StainedGlassStatusUpGroupId"]]:
            if r["StatusCalculationType"] == power.ADD:
                want[r["StatusKindType"]] += r["EffectValue"]
        con = model.rows_to_db({"user_important_items": {"sql": "create table user_important_items (user_id int, important_item_id int, count int)",
                                                          "rows": [{"user_id": 1, "important_item_id": item["ImportantItemId"], "count": 1}]}})
        s = model.Save(con, 1)
        self.assertEqual(power.stained_glass_status(t, s, target["TargetValue"], 0), [(power.ADD, want)])
        self.assertEqual(power.stained_glass_status(t, s, -1, 0), [(power.ADD, power.sv())])


if __name__ == "__main__":
    unittest.main()
