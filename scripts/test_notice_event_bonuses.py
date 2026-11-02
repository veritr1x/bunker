"""Reject unrelated quests, currencies, terms and invented ascension values."""
import copy,json,unittest
from pathlib import Path
from recover_notice_event_bonuses import recover,periods


class RecoverBonuses(unittest.TestCase):
    def setUp(self):
        self.tables={
            'm_event_quest_chapter':[[508,1,8,508,508,0,0,7,100,200]],
            'm_event_quest_sequence_group':[[7,1,8]],
            'm_event_quest_sequence':[[8,1,9]],
            'm_quest':[[9]+[0]*18+[10]],
            'm_quest_bonus':[[10,0,0,11]],
            'm_quest_bonus_weapon_group':[[11,310211,0,12],[11,310211,2,13]],
            'm_quest_bonus_effect_group':[[12,1,3,14],[13,1,3,15]],
            'm_quest_bonus_drop_reward':[[14,6,22,2],[15,6,22,8]],
            'm_consumable_item':[[22,110,0,0,0,'',110,22]],
        }
        self.texts={'quest.event.chapter_title.508':'Record: Coffin of Repose',
                    'consumable_item.name.110022':'Coffin of Repose Medal'}

    def recover(self,tables=None,windows=None,weapons=None):
        return recover(tables or self.tables,windows or [(110,190)],weapons or {310211},self.texts)

    def test_foreign_keys_and_ascension_thresholds(self):
        events,_=self.recover()
        bonus=events[0]['weapon_bonuses'][0]
        self.assertEqual(bonus['additional_drops_by_ascension'],[2,2,8,8,8])
        self.assertEqual(bonus['currency_name'],'Coffin of Repose Medal')
        self.assertEqual(events[0]['quest_bonus_ids'],[10])

    def test_wrong_weapon_and_nonoverlapping_event_are_rejected(self):
        self.assertEqual(self.recover(weapons={310011})[0],[])
        self.assertEqual(self.recover(windows=[(201,250)])[0],[])

    def test_missing_quest_link_cannot_create_event_association(self):
        t=copy.deepcopy(self.tables);t['m_quest'][0][19]=999
        self.assertEqual(self.recover(tables=t)[0],[])

    def test_unknown_first_ascension_bonus_is_not_filled_with_zero(self):
        t=copy.deepcopy(self.tables);t['m_quest_bonus_weapon_group']=t['m_quest_bonus_weapon_group'][1:]
        self.assertEqual(self.recover(tables=t)[0],[])

    def test_partial_date_terms_are_withheld(self):
        t=copy.deepcopy(self.tables)
        for r in t['m_quest_bonus_weapon_group']:r.append(1)
        t['m_quest_bonus_term_group']=[[1,1,120,180]]
        events,skipped=self.recover(tables=t)
        self.assertEqual(events,[]);self.assertEqual(len(skipped),2)

    def test_wrong_possession_type_is_not_a_consumable(self):
        t=copy.deepcopy(self.tables)
        for r in t['m_quest_bonus_drop_reward']:r[1]=5
        self.assertEqual(self.recover(tables=t)[0],[])

    def test_event_boxes_use_native_event_period(self):
        r={'baseline':{'start':1629943200000},'event':{'chapter':{
           'StartDatetime':1629943200000,'EndDatetime':1630893599000}}}
        self.assertEqual(periods(r),[(1629943200000,1630893599000)])

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'inputs/summon-notice-event-bonuses.json').is_file(),
                         'Requires the locally recovered historical bonus evidence.')
    def test_real_prisoner_snapshot_has_own_event_and_no_later_season(self):
        path=Path(__file__).resolve().parents[1]/'inputs/summon-notice-event-bonuses.json'
        data=json.loads(path.read_text(encoding='utf-8'))
        r=next(r for r in data['entries'] if r['gacha_id']==39)
        self.assertEqual(len(r['events']),1)
        event=r['events'][0]
        self.assertEqual(event['event_name'],'Record: Coffin of Repose')
        self.assertEqual({b['weapon_id'] for b in event['weapon_bonuses']},{310211,310011})
        for b in event['weapon_bonuses']:
            self.assertEqual(b['additional_drops_by_ascension'],[2,5,8,11,15])


if __name__=='__main__':unittest.main()
