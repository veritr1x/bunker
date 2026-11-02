"""Cross-check reconstructed notices against captured game facts and native data."""
import json,re,sys,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.build/notice-audit/python'))
from bs4 import BeautifulSoup
from rich_notice_content import RichNotices
from audit_reconstructed_notice_fidelity import audit


@unittest.skipUnless((ROOT/'inputs/bunker-notices-template-based.zip').is_file(),
                     'Requires the locally built notice pack, which contains game data.')
class Fidelity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ROOT/'inputs/bunker-notices-template-based.zip') as z:
            cls.pack=json.loads(z.read('notices.json'));cls.maps=json.loads(z.read('templates/base-map.json'))['matches'];cls.members=set(z.namelist())
            cls.runtime=json.loads(z.read('templates/runtime-facts.json'))['entries']
        cls.notices={n['id']:n for n in cls.pack['notices']}

    def doc(self,g):return BeautifulSoup(self.notices[1500000000+g]['body'],'html5lib')

    def test_all_203_pages_have_no_unresolved_rendering_or_content_errors(self):
        result=audit(self.pack,self.maps,self.members)
        self.assertEqual(result['audited_pages'],203)
        self.assertEqual(result['status_counts'],{'pass':202,'reviewed_payment_conflict':1})
        self.assertEqual(result['reviewed_exception_ids'],[405])

    def test_new_year_two_opportunities_keep_distinct_target_dates_and_one_use(self):
        first=re.sub(r'\s+([.,])',r'\1',self.doc(124).get_text(' ',strip=True));second=re.sub(r'\s+([.,])',r'\1',self.doc(970124).get_text(' ',strip=True))
        self.assertIn('Jan 02, 2022 17:59:59 PST',first)
        self.assertIn('Jan 10, 2022 17:59:59 PST',second)
        for body in [first,second]:
            self.assertIn('free 10x summon',body);self.assertIn('It can be used once.',body)
            self.assertNotIn('1 times',body);self.assertNotIn('per day',body)

    def test_elemental_tickets_keep_their_actual_element_and_illustrated_costumes(self):
        body=self.doc(970003).get_text(' ',strip=True)
        self.assertIn('★★★★ Fire weapon is guaranteed',body)
        self.assertIn('Characters Shown on the Banner',body)
        self.assertIn('About Summon Tickets',body)
        self.assertIn('Fire ★★★★ Guaranteed Summons Ticket',body)
        self.assertNotIn('Exchange Characters',body)

    def test_sr_ticket_is_not_mislabelled_as_four_star(self):
        n=self.notices[1500970002]
        self.assertIn('★★★ Guaranteed',n['title'])
        self.assertNotIn('★★★★ Guaranteed',n['title'])
        self.assertIn('★★★+ Premium Summon Ticket',self.doc(970002).get_text(' ',strip=True))

    def test_missing_art_uses_text_title_and_observed_paid_costs_without_fake_dates(self):
        for g in [70,85,160]:
            doc=self.doc(g);self.assertTrue(doc.select_one('.notice-title-panel'))
            body=doc.get_text(' ',strip=True)
            self.assertIn('3,000 paid gems',body)
            self.assertNotIn('2099',body)
        self.assertIn('★★★★ weapon is guaranteed',self.doc(160).get_text(' ',strip=True))

    def test_runtime_supplements_match_captured_cost_rows_and_not_sentinel_limits(self):
        added=[m for m in self.maps if m.get('fidelity',{}).get('phase_source')=='current_runtime_catalog']
        self.assertGreaterEqual(len(added),100)
        for m in added:
            g=m['gacha_id'];actual=m['rich_content']['configured_phase_facts'];source=self.runtime[str(g)]['cost_rows']
            self.assertEqual(len(actual),len(source),g)
            for a,s in zip(actual,source):
                self.assertEqual(a['draws'],s['draws'],g)
                self.assertNotEqual(a.get('limit'),999)
                if s['price_text'].endswith('paid gems'):self.assertEqual(a['cur'],'paid')
                if s['price_text']=='Free':self.assertEqual(a['price'],0)
        step=self.doc(507001).get_text(' ',strip=True)
        self.assertIn('Step 5',step);self.assertIn('appearance-rate multiplier ×2',step)
        self.assertIn("Piece: Zenith's Brilliance",step)

    def test_complete_event_rewards_include_native_named_filler_and_target_stock(self):
        body=self.doc(302001).get_text(' ',strip=True)
        self.assertIn('View all rewards by level',body)
        self.assertIn('Small Stamina Recovery',body)
        self.assertIn('Gems',body)
        m=next(m for m in self.maps if m['gacha_id']==302001)
        self.assertGreater(m['fidelity']['full_box_reward_rows'],50)

    def test_native_costume_bonus_is_restored_without_later_campaign_values(self):
        m=next(m for m in self.maps if m['gacha_id']==39)
        self.assertEqual(m['rich_content']['native_event_costume_bonus_rows'],[
            {'event_id':508,'costume_id':31005,'stat':'Attack','percent_by_ascension':[50,50,50,50,50]}])
        body=self.doc(39).get_text(' ',strip=True)
        self.assertIn('+50%',body)
        for wrong in ['Black Pearl','Passionflower','Season 005','+200%']:self.assertNotIn(wrong,body)

    def test_guarantee_count_and_element_are_not_discarded(self):
        self.assertEqual(RichNotices.guarantee({'guar':'r4c:fire','guaranteed_count':2}),
                         'At least 2 ★★★★ Fire character weapons are guaranteed.')

    def test_native_advertised_prices_override_generic_runtime_defaults(self):
        for g in [43,52,60]:
            body=self.doc(g).get_text(' ',strip=True)
            self.assertIn('1,500 paid gems',body);self.assertNotIn('3,000 paid gems',body)
        body=self.doc(9000034).get_text(' ',strip=True)
        for term in ['2,000 gems','Piece: Black Pearl','20 times']:self.assertIn(term,body)

    def test_exchange_options_are_not_granted_as_free_summon_bonuses(self):
        targets=[m for m in self.maps if any('/limited_139/' in p for p in m.get('fidelity',{}).get('native_promotion_sources',[]))]
        self.assertTrue(targets)
        for m in targets:
            self.assertEqual(m['rich_content']['configured_phase_facts'][0]['cur'],'free')
            self.assertFalse(m['rich_content']['configured_phase_facts'][0].get('bonus_display'))
            self.assertIn('Trade 50',self.doc(m['gacha_id']).get_text(' ',strip=True))

    def test_native_step_rewards_round_limits_and_slots_survive(self):
        body=self.doc(507001).get_text(' ',strip=True)
        for phrase in ['Skip Ticket','100','Advanced Handbook','3 times']:self.assertIn(phrase,body)
        body=self.doc(519001).get_text(' ',strip=True)
        self.assertIn('10th summon',body);self.assertIn('Topaz',body);self.assertIn('Tanzanite',body)

    def test_unrelated_catalog_guarantee_is_removed_from_nier_day_title(self):
        n=self.notices[1500000049]
        self.assertEqual(n['title'],'NieR Day Bonus Summons')
        self.assertIn('Advanced Handbook',self.doc(49).get_text(' ',strip=True))


if __name__=='__main__':unittest.main()
