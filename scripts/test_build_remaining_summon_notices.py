"""Check generated pages do not turn partial native data into historical claims."""
import copy
import json
import unittest
from pathlib import Path

import build_remaining_summon_notices as generated

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT/'inputs/remaining-summon-notice-evidence.json'
DATA = json.loads(PATH.read_text(encoding='utf-8')) if PATH.exists() else None
ROWS = {r['gacha_id']:r for r in DATA['generated']} if DATA else {}


@unittest.skipUnless(DATA, 'Requires local native/history evidence, which contains game data.')
class GeneratedNotices(unittest.TestCase):
    def test_all_203_evidence_records_validate(self):
        self.assertEqual(len(ROWS), 203)
        for r in ROWS.values():
            with self.subTest(gacha=r['gacha_id']):
                generated.validate_record(r)

    def test_every_generated_page_is_explicitly_labelled(self):
        for r in ROWS.values():
            if r.get('direct_notice_id'):continue
            page = generated.make_notice(r, 'native' if r['native_banner'] else None)
            self.assertFalse(page['title'].startswith('['))
            self.assertIn('original announcement text has not been recovered', page['body'])

    def test_historical_roster_contamination_is_rejected(self):
        r = copy.deepcopy(ROWS[10003])
        r['exchange']['lineup'].append({'costume_id':35011, 'price':150})
        with self.assertRaises(AssertionError):
            generated.validate_record(r)

    def test_early_two_character_weekly_retains_snapshot_roster(self):
        page = generated.make_notice(ROWS[10003], 'native')
        self.assertIn('Argo', page['body'])
        self.assertIn('Noelle', page['body'])
        self.assertIn('Fractured Traveler', page['body'])
        self.assertNotIn('Bloody Weapon', page['body'])
        self.assertIn('options visible in that snapshot', page['body'])

    def test_shared_automata_exchange_is_not_a_featured_volume_pool(self):
        for g in [45,46,150,151,513001]:
            text = generated.make_notice(ROWS[g], 'native')['body']
            self.assertIn('shared by several banners or volumes', text)
            self.assertIn('does not establish this banner’s featured characters', text)

    def test_original_run_dates_resolve_final_master_conflicts(self):
        for g in [10073,10074]:
            r=ROWS[g]
            self.assertEqual(r['direct_notice_id'],906)
            self.assertFalse(r['date_conflict'])
            self.assertEqual(r['historical_schedule_match']['end_minute']//60000,
                             (r['exchange']['conversion']-172800000)//60000)
            with self.assertRaises(AssertionError):generated.make_notice(r,'native')

    def test_wrong_conversion_cannot_be_used_for_direct_schedule_link(self):
        r=copy.deepcopy(ROWS[10073]);r['exchange']['conversion']+=172800000
        r['exchange']['medal_raw'][4]+=172800000
        with self.assertRaises(AssertionError):generated.validate_record(r)

    def test_placeholder_dates_and_missing_images_are_not_fabricated(self):
        for g in [60,70,85,160]:
            r = ROWS[g]
            page = generated.make_notice(r, 'native' if r['native_banner'] else None)
            self.assertNotIn('2099', page['body'])
            self.assertEqual(page['publish'], generated.LAUNCH)
        for g in [70,85,160]:
            page = generated.make_notice(ROWS[g], None)
            self.assertNotIn('thumb', page)
            self.assertNotIn('<img', page['body'])

    def test_missing_historical_snapshot_is_not_called_verified(self):
        for g in [94,9000035]:
            text = generated.make_notice(ROWS[g], 'native')['body']
            self.assertIn('final native master', text)
            self.assertIn('period-specific availability remains unverified', text)

    def test_reconstructed_event_boxes_are_not_original_reward_claims(self):
        events = [r for r in ROWS.values() if 'event' in r]
        self.assertEqual(len(events),14)
        for r in events:
            text = generated.make_notice(r, 'native')['body']
            self.assertIn('Bunker’s reconstructed box rewards', text)
            self.assertIn('not presented as original event facts', text)
        self.assertIn('Advanced Handbook',generated.make_notice(ROWS[302001],'native')['body'])
        self.assertNotIn('Item 311003',generated.make_notice(ROWS[302001],'native')['body'])

    def test_ticket_cost_uses_its_specific_native_ticket(self):
        text = generated.make_notice(ROWS[970009], 'native')['body']
        self.assertIn('Argo Guaranteed Summons Ticket', text)
        self.assertNotIn('Premium Summon Ticket', text)

    def test_free_banner_conflicts_do_not_publish_gem_costs(self):
        for g in [456,457,554,600,601,602,603,604,605,609,610]:
            text = generated.make_notice(ROWS[g], 'native')['body']
            self.assertIn('Payment configuration needs review', text)
            self.assertIn('disputed cost table is omitted', text)
            self.assertNotIn('3000', text)
            self.assertNotIn('Bunker summon options', text)

    def test_paid_banner_conflict_does_not_publish_unrestricted_gem_price(self):
        text = generated.make_notice(ROWS[405], 'native')['body']
        self.assertIn('Paid gems only', text)
        self.assertIn('does not restrict all options to paid gems', text)
        self.assertNotIn('Bunker summon options', text)

    def test_stale_japanese_title_uses_verified_english_native_banner(self):
        title = generated.make_notice(ROWS[580001], 'native')['title']
        self.assertIn('Mechanical Captain', title)
        self.assertNotIn('Hunter', title)

    def test_free_bonus_step_in_paid_sequence_is_not_a_payment_conflict(self):
        r = ROWS[9000086]
        self.assertEqual({s['cur'] for s in r['bunker_configuration']['steps']}, {'paid','free'})
        self.assertFalse(r['configuration_conflicts'])
        self.assertIn('Bunker summon options', generated.make_notice(r,'native')['body'])

    def test_generated_pages_do_not_replace_prior_125_repairs(self):
        old = json.loads((ROOT/'inputs/summon-notice-repair-evidence.json').read_text(encoding='utf-8'))
        prior = {r['gacha_id'] for r in old['direct']+old['reconstructed']}
        self.assertFalse(prior & ROWS.keys())
        self.assertEqual(len(prior | ROWS.keys()),328)


if __name__ == '__main__':
    unittest.main()
