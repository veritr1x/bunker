import unittest

from audit_summon_links import add_rules, audit_events, build_catalog, exact_event_notices, go_map, matches_title


def chapter(ident=509, title_id=509, start=1000):
    return {"EventQuestChapterId": ident, "NameEventQuestTextId": title_id,
            "EventQuestType": 1, "StartDatetime": start}


def notice(ident, title, start, kind=2):
    return {"id": ident, "title": title, "publish": start, "type": kind}


class NoticeLinks(unittest.TestCase):
    def test_different_rerun_and_coming_soon_are_not_substituted(self):
        rows = [notice(1, 'Event Quest "Record: Sunset Port" On Now', 500),
                notice(2, 'Event Quest "Record: Sunset Port" Coming Soon', 1000),
                notice(3, 'Event Quest "Record: Sunset Port" On Now', 1000)]
        self.assertEqual([n["id"] for n in exact_event_notices("Record: Sunset Port", 1000, rows)], [3])

    def test_typo_in_notice_category_does_not_hide_event(self):
        rows = [notice(1574, 'Resurrected Event Quest "Record: The Wishing Space" On Now', 1000, kind=3)]
        found = audit_events([chapter()], {"quest.event.chapter_title.509": "Record: The Wishing Space"}, rows)
        self.assertEqual(found[0]["notice_id"], 1574)

    def test_corrupted_quotation_mark_is_normalized(self):
        rows = [notice(1168, 'Resurrected Crossover Quest “Record: Vestiges of Paradiseâ€\x9d On Now', 1000)]
        self.assertEqual(len(exact_event_notices("Record: Vestiges of Paradise", 1000, rows)), 1)

    def test_ambiguous_pair_is_not_accepted(self):
        rows = [notice(i, 'Event Quest "Record: Sunset Port" On Now', 1000) for i in (1, 2)]
        found = audit_events([chapter()], {"quest.event.chapter_title.509": "Record: Sunset Port"}, rows)
        self.assertEqual(found[0]["status"], "ambiguous")
        self.assertEqual(found[0]["notice_id"], 0)

    def test_text_id_is_used_instead_of_chapter_id(self):
        rows = [notice(1631, 'Event Quest "Record: Foundation of Fortune" On Now', 1000)]
        found = audit_events([chapter(585, 522)], {"quest.event.chapter_title.522": "Record: Foundation of Fortune"}, rows)
        self.assertEqual(found[0]["notice_id"], 1631)

    def test_initials_are_not_expanded_generally_or_matched_inside_words(self):
        self.assertFalse(matches_title("Variation: A. Mage", "Variation: Aurora Mage On Now"))
        self.assertFalse(matches_title("Record: Sunset", "Record: Sunsetland On Now"))
        found = audit_events([chapter(300, 300)], {"quest.event.chapter_title.300": "Variation: A. Dynast"},
                             [notice(1244, 'Event Quest "Variation: Aurora Dynast" On Now', 1000)])
        self.assertTrue(found[0]["reviewed_alias"])
        self.assertEqual(found[0]["notice_id"], 1244)
        different_source = audit_events([chapter(300, 300)], {"quest.event.chapter_title.300": "Variation: A. Mage"},
                                       [notice(1244, 'Event Quest "Variation: Aurora Dynast" On Now', 1000)])
        self.assertFalse(different_source[0]["reviewed_alias"])
        self.assertEqual(different_source[0]["notice_id"], 0)

    def test_existing_entry_skips_added_rule_notice_and_pairs_use_base_snapshot(self):
        catalog = {10: {"start": 1000, "explicit_notice_id": 0}}
        rules = [{"id": 10, "asset": "limited_10", "notice": 123, "start": 1000, "steps": [{}]},
                 {"id": 20, "asset": "limited_20", "notice": 124, "pair": 10, "steps": [{}]},
                 {"id": 30, "asset": "limited_30", "pair": 20, "steps": [{}]}]
        add_rules(catalog, rules)
        self.assertEqual(catalog[10]["explicit_notice_id"], 0)
        self.assertEqual(catalog[20]["explicit_notice_id"], 124)
        self.assertEqual(catalog[20]["start"], 1000)
        self.assertNotIn(30, catalog)

    def test_loader_map_is_read_and_missing_map_fails(self):
        self.assertEqual(go_map("pairs", "var pairs = map[int32]int32{46: 45, 151: 150}"), {46: 45, 151: 150})
        self.assertEqual(go_map("skip", "var skip = map[int32]bool{617: true, 1: false}", True), {617: True, 1: False})
        with self.assertRaises(ValueError):
            go_map("absent", "")

    def test_catalog_requires_medal_or_special_and_valid_exchange_window(self):
        tables = {
            "GachaMedal": [{"ShopTransitionGachaId": 10, "ConsumableItemId": 1, "AutoConvertDatetime": 300000000},
                           {"ShopTransitionGachaId": 20, "ConsumableItemId": 2, "AutoConvertDatetime": 300000000},
                           {"ShopTransitionGachaId": 30, "ConsumableItemId": 3, "AutoConvertDatetime": 100000000}],
            "MomBanner": [{"DestinationDomainType": 1, "DestinationDomainId": i,
                           "BannerAssetName": "limited_" + str(i), "StartDatetime": 1000}
                          for i in (10, 40, 50)],
            "ShopItem": [{"ShopItemId": i, "PriceId": i} for i in (1, 2, 3)],
            "ShopItemCell": [{"ShopItemCellId": i, "ShopItemId": i} for i in (1, 2, 3)],
            "ShopItemCellGroup": [{"ShopItemCellGroupId": 1, "ShopItemCellId": i} for i in (1, 2, 3)],
            "Shop": [{"ShopItemCellGroupId": 1, "StartDatetime": 1000}],
            "EventQuestChapter": [],
        }
        patch = "\n".join("+var " + name + " = map[int32]" + typ + "{}" for name, typ in
                          (("sharedMedalGachas", "int32"), ("medalItemGachas", "int32"),
                           ("parkedReruns", "int64"), ("bannerlessSkipped", "bool")))
        catalog = build_catalog(tables.__getitem__, [], [], patch, "\n 50: specialFree,")
        self.assertEqual(set(catalog), {10, 20, 50})
        self.assertEqual(catalog[20]["source"], "medal_exchange")


if __name__ == "__main__":
    unittest.main()
