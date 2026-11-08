#!/usr/bin/env python3
"""What event_runs.py records for each earlier run of a rerun event."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import event_runs as er  # noqa: E402


def tables(link=17, medal=25, quests=(1, 2), bonus_layout="2021"):
    """One event chapter (510) in one master: link 17 -> shop 6008 paying medal 25."""
    t = {
        "m_event_quest_chapter": [{"EventQuestChapterId": 510, "EventQuestLinkId": link, "EventQuestDisplayItemGroupId": 200011,
                                   "EventQuestSequenceGroupId": 9}],
        "m_event_quest_link": [{"EventQuestLinkId": link, "DestinationDomainType": 3, "DestinationDomainId": 6008,
                                "PossessionType": 6, "PossessionId": medal}],
        "m_event_quest_sequence_group": [{"EventQuestSequenceGroupId": 9, "DifficultyType": 1, "EventQuestSequenceId": 90}],
        "m_event_quest_sequence": [{"EventQuestSequenceId": 90, "SortOrder": i, "QuestId": q} for i, q in enumerate(quests, 1)],
        "m_quest": [{"QuestId": q, "QuestPickupRewardGroupId": 1000 + q, "QuestBonusId": 77} for q in quests],
        "m_quest_pickup_reward_group": [{"QuestPickupRewardGroupId": 1000 + q, "SortOrder": 1, "BattleDropRewardId": 5000 + q} for q in quests],
        "m_battle_drop_reward": [{"BattleDropRewardId": 5000 + q, "PossessionType": 6, "PossessionId": medal, "Count": 9} for q in quests],
        "m_quest_bonus": [{"QuestBonusId": 77, "QuestBonusCharacterGroupId": 1, "QuestBonusCostumeGroupId": 2, "QuestBonusWeaponGroupId": 3,
                           "QuestBonusCostumeSettingGroupId": 4}],
        "m_quest_bonus_character_group": [{"QuestBonusCharacterGroupId": 1, "CharacterId": 1001, "QuestBonusEffectGroupId": 11}],
        "m_quest_bonus_weapon_group": [{"QuestBonusWeaponGroupId": 3, "WeaponId": 300, "LimitBreakCountLowerLimit": 2, "QuestBonusEffectGroupId": 12}],
        "m_quest_bonus_effect_group": [{"QuestBonusEffectGroupId": 11, "QuestBonusEffectId": 101},
                                       {"QuestBonusEffectGroupId": 12, "QuestBonusEffectId": 102},
                                       {"QuestBonusEffectGroupId": 13, "QuestBonusEffectId": 103},
                                       {"QuestBonusEffectGroupId": 14, "QuestBonusEffectId": 104}],
        "m_quest_bonus_drop_reward": [{"QuestBonusEffectId": 102, "PossessionType": 6, "PossessionId": medal, "AdditionalCount": 5},
                                      {"QuestBonusEffectId": 103, "PossessionType": 6, "PossessionId": medal, "AdditionalCount": 2},
                                      {"QuestBonusEffectId": 104, "PossessionType": 6, "PossessionId": medal, "AdditionalCount": 3}],
    }
    if bonus_layout == "2021":
        del t["m_quest_bonus"][0]["QuestBonusCostumeSettingGroupId"]  # no such column yet
        t["m_quest_bonus_costume_group"] = [{"QuestBonusCostumeGroupId": 2, "CostumeId": 21001, "QuestBonusEffectGroupId": 13}]
    else:
        t["m_quest_bonus_costume_setting_group"] = [{"QuestBonusCostumeSettingGroupId": 4, "CostumeId": 21001, "LimitBreakCountLowerLimit": 1,
                                                     "QuestBonusEffectGroupId": 14, "QuestBonusTermGroupId": 1}]
    return t


class Pick(unittest.TestCase):
    def test_the_newest_master_published_during_the_run(self):
        self.assertEqual(er.pick([10, 20, 30, 40], (15, 35)), 30)

    def test_a_run_no_master_falls_in_takes_the_newest_before_it(self):
        self.assertEqual(er.pick([10, 20, 40], (25, 35)), 20)


class RunView(unittest.TestCase):
    def test_link_shown_medal_quests_and_drops(self):
        run = er.run_view(tables(), 510)
        self.assertEqual((run["link"], run["display"]), (17, 200011))
        self.assertEqual(run["quests"], [1, 2])
        self.assertEqual(run["drops"], {"1": [[6, 25, 9]], "2": [[6, 25, 9]]})

    def test_a_quest_without_drops_records_none(self):
        t = tables()
        t["m_quest"][0]["QuestPickupRewardGroupId"] = 0
        self.assertEqual(er.run_view(t, 510)["drops"]["1"], [])

    def test_bonuses_with_the_2021_costume_table(self):
        run = er.run_view(tables(), 510)
        rules = run["bonuses"][run["bonus"]["1"]]
        # The character's effect pays nothing (a stat effect): not listed.
        self.assertEqual(rules, [["costume", 21001, 0, [[6, 25, 2]]], ["weapon", 300, 2, [[6, 25, 5]]]])
        self.assertEqual(run["bonus"]["1"], run["bonus"]["2"])  # one definition, shared

    def test_bonuses_with_the_later_costume_table(self):
        run = er.run_view(tables(bonus_layout="later"), 510)
        self.assertIn(["costume", 21001, 1, [[6, 25, 3]]], run["bonuses"][run["bonus"]["1"]])

    def test_the_link_row_as_it_was(self):
        # A link id can be rewritten by a later run (chapter 512's link 20): the run keeps its own row.
        self.assertEqual(er.run_view(tables(), 510)["link_row"], {"shop": 6008, "possession_type": 6, "possession_id": 25})

    def test_a_bonus_paying_another_events_medal_is_left_out(self):
        t = tables()
        t["m_quest_bonus_drop_reward"].append({"QuestBonusEffectId": 102, "PossessionType": 6, "PossessionId": 93, "AdditionalCount": 11})
        run = er.run_view(t, 510)
        self.assertIn(["weapon", 300, 2, [[6, 25, 5]]], run["bonuses"][run["bonus"]["1"]])
        self.assertEqual(run["stale_bonus_medals"], [93])

    def test_a_chapter_missing_from_the_master(self):
        self.assertIsNone(er.run_view(tables(), 999))


class ChapterRuns(unittest.TestCase):
    """Which runs need their own data: those that differ from the final game data."""

    def test_a_run_like_the_final_game_data_needs_none(self):
        final = er.run_view(tables(), 510)
        self.assertIsNone(er.chapter_runs([(1, 2)], final, lambda run: dict(final, master="x")))

    def test_an_earlier_run_with_its_own_medal_is_recorded_and_the_last_is_not(self):
        final = er.run_view(tables(medal=149), 510)
        then = er.run_view(tables(medal=25), 510)
        out = er.chapter_runs([(1, 2), (3, 4)], final, lambda run: then if run == (1, 2) else final)
        self.assertEqual(out[0]["link_row"]["possession_id"], 25)
        self.assertIsNone(out[1])

    def test_a_single_run_whose_drops_were_rewritten_is_recorded(self):
        # Coffin of Repose ran once (2021); its quests were switched to a rerun's medals that never ran.
        final = er.run_view(tables(medal=53), 510)
        final["link_row"]["possession_id"] = 22
        then = er.run_view(tables(medal=22), 510)
        out = er.chapter_runs([(1, 2)], final, lambda run: then)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["drops"]["1"], [[6, 22, 9]])


if __name__ == "__main__":
    unittest.main()
