import copy,unittest
from native_notice_costume_bonus import recover_costume_bonuses


class CostumeBonus(unittest.TestCase):
    def setUp(self):
        self.tables={'m_quest_bonus':[[1,0,2,0]],'m_quest_bonus_costume_group':[[2,31005,3]],
          'm_quest_bonus_effect_group':[[3,1,1,4]],'m_quest_bonus_ability':[[4,5,1]],
          'm_ability':[[5,6]],'m_ability_level_group':[[6,0,7]],'m_ability_detail':[[7,0,0,8]],
          'm_ability_behaviour_group':[[8,0,9]],'m_abiliwy_behaviour':[[9,3,10]],
          'm_ability_behaviour_action_status':[[10,2,8,4,11]],
          'm_ability_status':[[11,0,500,0,0,0,0,0]]}

    def get(self):return recover_costume_bonuses(self.tables,{1},{31005},100,200)

    def test_historical_typo_is_followed_to_the_actual_action(self):
        self.assertEqual(self.get()[0]['stat_percent_by_ascension'],{'Attack':[50]*5})

    def test_flat_status_action_is_not_presented_as_a_percentage(self):
        self.tables['m_ability_behaviour_action_status'][0][1]=1
        self.assertEqual(self.get(),[])

    def test_missing_behaviour_never_joins_by_reusing_the_ability_id(self):
        self.tables['m_abiliwy_behaviour']=[]
        self.assertEqual(self.get(),[])

    def test_conditional_attributes_are_not_shown_as_unconditional_bonuses(self):
        self.tables['m_ability_behaviour_action_status'][0][2]=2
        self.assertEqual(self.get(),[])


if __name__=='__main__':unittest.main()
