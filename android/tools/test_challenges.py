#!/usr/bin/env python3
"""Pod Programs › Mods › Challenges: the game data changes behind Hard enemies,
Weakness only and Slow skills. Uses the real master data; skipped without it.
Needs the Android Python requirements and prepared sources."""
from pathlib import Path
import math, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
import android_calendar as cal  # noqa: E402
import android_challenges as ch  # noqa: E402

ORIGINAL = root / "inputs/20240404193219.bin.e"


class Challenges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORIGINAL.is_file():
            raise unittest.SkipTest("needs inputs/20240404193219.bin.e")
        cls.toc, cls.blob = cal.read_master(ORIGINAL)

    def rows(self, table, changed=None):
        return ch.records(self.toc, self.blob, changed or {}, table)

    def test_hard_enemies_doubles_enemy_stats(self):
        changed = {}
        n = ch.hard_enemies(self.toc, self.blob, changed, 2)
        self.assertGreaterEqual(n, 9400)
        before, after = self.rows("m_battle_npc_costume"), self.rows("m_battle_npc_costume", changed)
        big_hunt = ch.big_hunt_costumes(self.toc, self.blob, {})
        self.assertTrue(big_hunt)
        linear = ch.linear_enemy_costumes(self.toc, self.blob, {})
        doubled = 0
        for b, a in zip(before, after):
            if b["CostumeId"] < 1_000_000 or (b["BattleNpcId"], b["BattleNpcCostumeUuid"]) in big_hunt:
                self.assertEqual(a["Level"], b["Level"], b)  # allies, mirror decks and subjugation bosses stay
            elif b["CostumeId"] in linear:
                self.assertEqual(a["Level"], b["Level"] * 2, b)
                doubled += 1
        self.assertGreaterEqual(doubled, 9000)

    def test_hard_enemies_rounding_and_cubic(self):
        changed = {}
        ch.hard_enemies(self.toc, self.blob, changed, 1.5)
        before, after = self.rows("m_battle_npc_costume"), self.rows("m_battle_npc_costume", changed)
        linear = ch.linear_enemy_costumes(self.toc, self.blob, {})
        big_hunt = ch.big_hunt_costumes(self.toc, self.blob, {})
        stats = ch.stat_sum(self.toc, self.blob, {})
        odd = cubic = 0
        for b, a in zip(before, after):
            if b["CostumeId"] < 1_000_000 or (b["BattleNpcId"], b["BattleNpcCostumeUuid"]) in big_hunt:
                continue
            if b["CostumeId"] in linear and b["Level"] % 2:
                self.assertEqual(a["Level"], int(b["Level"] * 1.5 + 0.5))
                odd += 1
            elif b["CostumeId"] not in linear:
                want = 1.5 * stats(b["CostumeId"], b["Level"])
                self.assertLess(abs(stats(a["CostumeId"], a["Level"]) - want), want * 0.02, b)
                cubic += 1
            self.assertLess(a["Level"], 2**31)
        self.assertGreater(odd, 0)
        self.assertGreater(cubic, 0)

    def test_hard_enemies_stats_stay_in_range_at_every_setting(self):
        # Some enemies' curves peak and fall (concave): past the peak a ×N
        # target can't be reached, and the level stays at the peak.
        stats = ch._stat_functions(self.toc, self.blob, {})
        for factor in (1.5, 2, 3, 5):
            changed = {}
            ch.hard_enemies(self.toc, self.blob, changed, factor)
            for b, a in zip(self.rows("m_battle_npc_costume"), self.rows("m_battle_npc_costume", changed)):
                before = [ch.evaluate(t, p, b["Level"]) for t, p in stats.get(b["CostumeId"], [])]
                if sum(before) <= 0:  # stats not from these curves: no change that matters
                    continue
                if a["Level"] == b["Level"]:
                    continue
                values = [ch.evaluate(t, p, a["Level"]) for t, p in stats[a["CostumeId"]]]
                self.assertTrue(all(0 <= v < 2**31 for v in values), (factor, b, values))
                self.assertTrue(all(v > 0 for v, w in zip(values, before) if w > 0), (factor, b, values))
                self.assertGreater(sum(values), sum(before), (factor, b))

    def test_weakness_only(self):
        changed = {}
        ch.weakness_only(self.toc, self.blob, changed)
        for b, a in zip(self.rows("m_battle_attribute_damage_coefficient_group"),
                        self.rows("m_battle_attribute_damage_coefficient_group", changed)):
            if b["AttributeDamageCoefficientGroupId"] == 1 and b["DamageCoefficientPermil"] <= 1000:
                self.assertEqual(a["DamageCoefficientPermil"], b["DamageCoefficientPermil"] // 2)
            else:  # weakness hits, the enemies' side and the Arena's (scheme 2) stay
                self.assertEqual(a, b)

    def test_slow_skills(self):
        changed = {}
        self.assertGreaterEqual(ch.slow_skills(self.toc, self.blob, changed), 27000)
        player = ch.player_skill_details(self.toc, self.blob, {})
        before = {r["SkillDetailId"]: r for r in self.rows("m_skill_detail")}
        after = {r["SkillDetailId"]: r for r in self.rows("m_skill_detail", changed)}
        some = next(d for d in sorted(player) if before[d]["SkillCooltimeValue"] > 0)
        self.assertEqual(after[some]["SkillCooltimeValue"], math.ceil(before[some]["SkillCooltimeValue"] * 1.5))
        enemy_only = next(d for d in sorted(before) if d not in player and before[d]["SkillCooltimeValue"] > 0)
        self.assertEqual(after[enemy_only], before[enemy_only])
        self.assertFalse([t for t in changed if t.startswith("m_skill_cooltime_behaviour")])

    def test_transform_off_writes_nothing(self):
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "out.bin.e"
            self.assertFalse(ch.transform(ORIGINAL, out, {"hardEnemies": 1, "weaknessOnly": False, "slowSkills": False}))
            self.assertFalse(out.exists())

    def test_stat_curves_untouched(self):
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "out.bin.e"
            self.assertTrue(ch.transform(ORIGINAL, out, {"hardEnemies": 2, "weaknessOnly": True, "slowSkills": True}))
            toc, blob = cal.read_master(out)
        for table in ("m_numerical_function", "m_numerical_function_parameter_group", "m_costume_status_calculation"):
            o1, l1 = self.toc[table]
            o2, l2 = toc[table]
            self.assertEqual(bytes(self.blob[o1:o1 + l1]), bytes(blob[o2:o2 + l2]), table)


if __name__ == "__main__":
    unittest.main()
