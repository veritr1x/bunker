"""Guard against carrying later-run details into historical summaries."""
import copy
import json
import unittest
from pathlib import Path

import build_summon_notice_repair_pack as repair

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT/'inputs/summon-notice-repair-evidence.json'
EVIDENCE = json.loads(EVIDENCE_PATH.read_text(encoding='utf-8')) if EVIDENCE_PATH.exists() else None
TARGETS = {r['gacha_id']: r for r in EVIDENCE['reconstructed']} if EVIDENCE else {}


@unittest.skipUnless(EVIDENCE, 'Requires the local reviewed reconstruction evidence, which contains game data.')
class RepairTests(unittest.TestCase):
    def test_2021_medal_retains_ceiling_and_omits_rate(self):
        m = repair.medal_fields([98003, 200, 98003, 8, 1633831199000])
        self.assertEqual((m['ceiling'], m['currency'], m['gacha']), (200, 98003, 8))
        self.assertNotIn('rate', m)

    def test_all_historical_lineups_and_prices_validate(self):
        for t in TARGETS.values():
            with self.subTest(gacha=t['gacha_id']):
                repair.validate_history(t)

    def test_extra_historical_costume_is_rejected(self):
        t = copy.deepcopy(TARGETS[10030])
        t['history']['historical_exchange_lineup'].append(999999)
        with self.assertRaises(AssertionError):
            repair.validate_history(t)

    def test_later_rerun_price_is_rejected_for_original_replicant(self):
        t = copy.deepcopy(TARGETS[8])
        t['history']['historical_exchange_evidence'][0]['item'][6] = 150
        with self.assertRaises(AssertionError):
            repair.validate_history(t)

    def test_changed_original_banner_period_is_rejected(self):
        t = copy.deepcopy(TARGETS[8])
        t['end'] += repair.DAY
        with self.assertRaises(AssertionError):
            repair.validate_history(t)

    def test_griff_omits_later_costume_and_rates(self):
        t = TARGETS[10030]
        self.assertTrue(t['roster_removed_from_reference'])
        notice = repair.reconstructed_notice(t, 'native')
        self.assertNotIn('Bloody Captain', notice['body'])
        self.assertIn('additional costume', notice['body'])
        self.assertIn('inferred', notice['body'])
        self.assertIn('have not been verified', notice['body'])

    def test_paid_original_does_not_clone_later_step_guarantees(self):
        notice = repair.reconstructed_notice(TARGETS[515001], 'native')
        self.assertIn('200 shards', notice['body'])
        self.assertNotIn('Step 3', notice['body'])
        self.assertNotIn('Awakening Stone', notice['body'])
        self.assertFalse(notice['title'].startswith('['))

    def test_free_and_paid_ffxiv_currency_and_prices_remain_distinct(self):
        free, paid = TARGETS[159], TARGETS[517001]
        self.assertNotEqual(free['medal']['ConsumableItemId'], paid['medal']['ConsumableItemId'])
        self.assertEqual(free['history']['historical_exchange_prices'], [200])
        self.assertEqual(paid['history']['historical_exchange_prices'], [150])

    def test_existing_links_cannot_be_overwritten(self):
        pack = {'notices': [{'id': 1}, {'id': 2}], 'gacha': {'10': 1}}
        with self.assertRaises(AssertionError):
            repair.add_links(pack, {10: 2})

    def test_direct_links_and_conflicting_dates_are_disjoint(self):
        direct = {r['gacha_id'] for r in EVIDENCE['direct']}
        synthetic = set(TARGETS)
        conflicts = {r['gacha_id'] for r in EVIDENCE['review_only']}
        self.assertFalse((direct | synthetic) & conflicts)
        self.assertEqual((len(direct), len(synthetic), len(conflicts)), (106, 19, 2))
        self.assertEqual(328-len(direct | synthetic), 203)


if __name__ == '__main__':
    unittest.main()
