#!/usr/bin/env python3
"""The notices build_event_notices.py rebuilds for home banners whose notice was lost."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_event_notices as ben  # noqa: E402

JUL28 = 1627509600000  # 2021-07-28 22:00 UTC
SEP8 = 1631138399000   # 2021-09-08 21:59:59 UTC


class Pages(unittest.TestCase):
    FACTS = {"name": "Record: The Cage of Reincarnation", "family": "record", "start": JUL28, "end": SEP8, "crossover": True,
             "medal": {"id": 110025, "name": "Automata Medal", "plural": "Automata Medals", "icon": "img/m.webp"},
             "exchange": "Automata Medal Exchange", "exclusive": [], "weapon_bonus": [], "costume_bonus": []}

    def test_an_event_banner_announces_its_event_as_officially(self):
        n = ben.make_notice(2, "event_mom_banner_500", (JUL28, SEP8), self.FACTS, "img/" + "ab" * 32 + ".webp")
        self.assertEqual((n["id"], n["type"], n["publish"]), (1_600_000_002, 2, JUL28))
        self.assertEqual(n["title"], 'Crossover Quest "Record: The Cage of Reincarnation" On Now')
        self.assertEqual(n["thumb"], "ab" * 32)
        body = n["body"]
        for text in ("Hello, and thank you for playing NieR Re[in]carnation.<br /> <br /> The Crossover Quest", "Jul. 28 at 14:00 PST", "Jul. 28 14:00 - Sept. 8 13:59 PST",
                     "Automata Medals", "Automata Medal Exchange", "<h3>Duration</h3>", "<h3>How to Play Event Quests</h3>",
                     "<h3> Notes </h3>", "This event may reappear in the future."):
            self.assertIn(text, body)
        self.assertNotIn("message from the management team", body)
        self.assertNotIn("rebuilt", body)

    def test_a_banner_without_an_event_says_what_it_advertised(self):
        n = ben.make_notice(28, "campaign_937", (JUL28, SEP8), None, None)
        self.assertEqual((n["type"], n["title"]), (1, "Campaign On Now"))
        self.assertNotIn("thumb", n)
        self.assertNotIn("rebuilt", n["body"])
        self.assertNotIn("<img", n["body"])

    def test_names_are_escaped(self):
        n = ben.make_notice(9, "event_mom_banner_1", (JUL28, SEP8), dict(self.FACTS, name="A <b> & C", crossover=False), None)
        self.assertIn("A &lt;b&gt; &amp; C", n["body"])

    def test_kinds(self):
        self.assertEqual([ben.kind(n) for n in ("campaign_931", "mission_mom_banner_936_01", "main_quest_mom_banner_012",
                                                 "main_quest_vh_mom_banner_1", "big_hunt_mom_banner_1", "limited_45")],
                         ["Campaign", "Missions", "Main Story", "Main Story", "Subjugation", "Notice"])


class ComingSoon(unittest.TestCase):
    def test_a_banner_before_its_event_announces_it(self):
        runs = {702: [(JUL28 + 10 * 86_400_000, SEP8)]}
        self.assertEqual(ben.coming(702, JUL28, runs), (702, 0))
        self.assertIsNone(ben.coming(702, SEP8 + 1, runs))

    def test_the_coming_soon_page(self):
        n = ben.make_notice(67, "event_mom_banner_702", (JUL28, SEP8), None, None,
                            soon={"name": "Abyss Tower: Burning Prison", "start": JUL28 + 86_400_000})
        self.assertEqual((n["type"], n["title"]), (2, 'Event Quest "Abyss Tower: Burning Prison" Coming Soon'))
        self.assertIn("will be available starting Jul. 29 at 14:00 PST", n["body"])


class Items(unittest.TestCase):
    """Possession type 6 names an item by its id; its name and icon follow its asset ids."""

    def test_an_item_is_named_by_its_asset(self):
        import event_notice_facts as F
        rows = {12: {"ConsumableItemId": 12, "AssetCategoryId": 110, "AssetVariationId": 19}}
        texts = {"consumable_item.name.110019": "City of Discontent Medal"}
        self.assertEqual(F.item_key(rows, 12), "110019")
        self.assertEqual(F.item_name(texts, "110019"), "City of Discontent Medal")
        self.assertIsNone(F.item_key(rows, 13))

    def test_a_lost_icon_is_the_same_named_items(self):
        import event_notice_facts as F
        texts = {"consumable_item.name.110045": "Bronze Seat of Shadow Medal",
                 "consumable_item.name.110218": "Bronze Seat of Shadow Medal",
                 "consumable_item.name.110219": "Silver Seat of Shadow Medal"}
        self.assertEqual(F.icon_keys(texts, "110045"), ["110045", "110218"])


class Portraits(unittest.TestCase):
    def test_art_fits_the_panel_box_at_twice_its_size(self):
        import event_notice_facts as F
        from PIL import Image
        tall = Image.new("RGBA", (900, 1400), (200, 0, 0, 255))
        out = F.fit_portrait(tall)
        self.assertEqual(out.size, (460, 426))
        box = out.getchannel("A").getbbox()
        self.assertEqual(box[3], 426)  # standing on the bottom edge
        self.assertLessEqual(box[2] - box[0], 460)


class Exclusive(unittest.TestCase):
    def test_how_to_play_names_the_exclusive_character(self):
        import event_notice_pages as pages
        costume = {"character": "Argo", "costume": "Summer Traveler"}
        facts = dict(Pages.FACTS, exclusive=[{"costume": costume, "weapon": None}])
        text = pages.how_to_play_record(facts)
        self.assertIn('for the event-exclusive character <span class="text-red">Summer Traveler</span> as well as', text)
        self.assertNotIn("{", text)


class Tables(unittest.TestCase):
    def test_rows_with_the_same_bonus_share_their_cells(self):
        import event_notice_pages as pages
        rows = [("img/a.webp", "Blackened Will", [1, 3, 5, 7, 10], ("img/m.webp",)),
                ("img/b.webp", "Black Lily", [5, 11, 17, 23, 30], ("img/m.webp",)),
                ("img/c.webp", "Spiral Dreams", [5, 11, 17, 23, 30], ("img/m.webp",))]
        html = pages.bonus_table(rows, "Weapon")
        self.assertEqual(html.count('rowSpan="2" style="text-align:center">+'), 5)
        self.assertEqual(html.count("<tr> <th>"), 3)
        self.assertIn('<td style="text-align:center">+1</td>', html)


class Events(unittest.TestCase):
    def test_the_event_whose_run_starts_with_the_banner(self):
        names = {510: "Record: The Cage of Reincarnation", 911: "Character Quest", 99012: "Dark Memory", 220004: "Dungeon: Aberrant Memories"}
        runs = {510: [(JUL28, SEP8)], 911: [(JUL28, SEP8)], 99012: [(JUL28, SEP8)], 220004: [(JUL28, SEP8)]}
        self.assertEqual(ben.event_at(JUL28, runs, names), (510, 0))
        self.assertIsNone(ben.event_at(JUL28 + 1, runs, names))

    def test_a_later_run_is_found_by_its_index(self):
        runs = {509: [(1, 2), (JUL28, SEP8)]}
        self.assertEqual(ben.event_at(JUL28, runs, {509: "Record: Sunset Port"}), (509, 1))


class Art(unittest.TestCase):
    def test_the_strip_is_cut_out_of_its_transparent_square(self):
        from PIL import Image
        square = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        square.paste(Image.new("RGBA", (450, 230), (200, 10, 10, 255)), (31, 141))
        self.assertEqual(ben.trim(square).size, (450, 230))


if __name__ == "__main__":
    unittest.main()
