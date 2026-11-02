"""Validate base selection without carrying over unrelated run facts."""
import copy,json,unittest,zipfile
from pathlib import Path
try:
    import build_notice_templates as templates
except ModuleNotFoundError:
    templates=None

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'inputs/bunker-notices-complete-generated.zip'


@unittest.skipUnless(templates and PACK.exists(),'Requires local notice/evidence inputs and BeautifulSoup.')
class NoticeTemplates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(PACK) as z:cls.pack=json.loads(z.read('notices.json'))
        cls.notices={n['id']:n for n in cls.pack['notices']}
        cls.entries=templates.target_records()

    def test_exact_and_campaign_matches_validate_all_seventeen(self):
        pairs={**templates.EXACT,**templates.CAMPAIGN}
        self.assertEqual(len(pairs),17)
        for g,n in pairs.items():
            with self.subTest(gacha=g):
                self.assertTrue(templates.validate_direct(g,self.entries[g],self.notices[n]))

    def test_wrong_free_campaign_is_rejected_even_when_the_format_matches(self):
        with self.assertRaises(AssertionError):
            templates.validate_direct(601,self.entries[601],self.notices[903])

    def test_free_crossover_must_use_its_explicit_campaign_section(self):
        with self.assertRaises(StopIteration):
            templates.validate_direct(554,self.entries[554],self.notices[1411])

    def test_date_parser_handles_year_rollover(self):
        start,end=templates.date_pairs('Dec. 31 18:00 - Jan. 15 17:59 PST',2022)[0]
        self.assertIn('2022',templates.common.date(start))
        self.assertIn('2023',templates.common.date(end))

    def test_premium_ticket_payment_option_does_not_make_a_normal_banner_a_ticket_notice(self):
        r=self.entries[38]['record']
        self.assertEqual(templates.payment(self.entries[38]['title'],r),'gems')
        self.assertEqual(templates.family(self.entries[38]['title'],r),'premium')

    def adapted(self,g,base_id):
        entry=self.entries[g];n=self.notices[templates.SYNTH+g]
        mapping={}
        return templates.adapt(n,entry,self.notices[base_id],mapping),mapping

    def test_replicant_original_price_is_kept(self):
        n,m=self.adapted(8,1050)
        self.assertIn('200 shards',n['body'])
        self.assertNotIn('reference rerun uses 150',n['body'])
        self.assertIn('reference rerun uses 150',''.join(m['player_ui_removed_html']))
        self.assertIn('Duration',n['body'])
        self.assertIn('exchange',m['adapted_section_order'])

    def test_griff_does_not_gain_later_bloody_costume(self):
        entry=self.entries[10030];nid=entry['record']['reference_notice_id']
        n,m=self.adapted(10030,nid)
        self.assertNotIn('Bloody Captain',n['body'])
        self.assertIn('Estimated Period',n['body'])
        self.assertNotIn('inferred',n['body'])

    def test_source_rewards_and_images_are_not_carried_over(self):
        entry=self.entries[34];original=self.notices[templates.SYNTH+34]
        base={'id':999,'title':'Template source','body':'<section><h3>Duration</h3><p>Jan. 1 0:00 - Jan. 2 0:00 PST</p><h3>Summons Details</h3><p>DIFFERENT REWARD x999</p><img src="img/WRONG_ART.webp"><h3>Notes</h3></section>'}
        n=templates.adapt(original,entry,base,{})
        self.assertNotIn('DIFFERENT REWARD',n['body'])
        self.assertNotIn('WRONG_ART',n['body'])
        self.assertNotIn('Jan. 2 0:00',n['body'])
        self.assertEqual(n.get('thumb'),original.get('thumb'))

    def test_event_uses_original_section_order_without_source_bonuses(self):
        n,m=self.adapted(302001,1015)
        self.assertIn('howto',m['adapted_section_order'])
        self.assertIn('eventbox',m['adapted_section_order'])
        self.assertIn('Blackbird Greatsword',n['body'])
        self.assertNotIn('Quest Bonus: Resonant',n['body'])
        self.assertNotIn('not presented as original event facts',n['body'])
        self.assertIn('not presented as original event facts',''.join(m['player_ui_removed_html']))

    def test_unknown_art_and_dates_remain_unknown(self):
        n,m=self.adapted(70,962)
        self.assertNotIn('2099',n['body'])
        self.assertNotIn('<img',n['body'])
        self.assertNotIn('Placeholder dates',n['body'])
        self.assertIn('Placeholder dates',''.join(m['player_ui_removed_html']))

    def test_payment_conflict_still_withholds_disputed_cost(self):
        n,m=self.adapted(405,989)
        self.assertNotIn('disputed cost table is omitted',n['body'])
        self.assertIn('disputed cost table is omitted',''.join(m['player_ui_removed_html']))
        self.assertNotIn('3000',n['body'])

    def test_default_ticket_label_uses_native_premium_ticket_not_stamina_item(self):
        n,m=self.adapted(38,1012)
        self.assertIn('Premium Summon Ticket',n['body'])
        self.assertNotIn('Small Stamina Recovery',n['body'])
        self.assertEqual(m['target_data_corrections'][0]['corrected'],'Premium Summon Ticket')

    def test_monthly_schedule_and_new_run_facts_are_not_inferred_from_base(self):
        n,m=self.adapted(124,903)
        self.assertNotIn('maximum of x200',n['body'])
        self.assertNotIn('per day',n['body'])
        self.assertFalse(n['title'].startswith('['))


if __name__=='__main__':unittest.main()
