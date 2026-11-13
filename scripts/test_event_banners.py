#!/usr/bin/env python3
"""Which banner event_banners.py records for each run and home-screen row."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import event_banners as eb  # noqa: E402

DAY = eb.DAY
EVERY = {f"ui)quest){lang})banner)event_banner_{i}" for lang in eb.LANGUAGES for i in (509, 535, 982)} | \
        {f"ui)quest){lang})mom_banner)event_mom_banner_{i}" for lang in eb.LANGUAGES for i in (500, 510)}


class Chapters(unittest.TestCase):
    def at(self, banners):
        """A master lookup: the banner of chapter 509 from a time on."""
        return lambda t: {509: next(b for since, b in sorted(banners, reverse=True) if since <= t)}

    def test_each_run_records_the_banner_live_in_its_middle(self):
        runs = {"509": [[0, 20 * DAY], [100 * DAY, 120 * DAY], [200 * DAY, 220 * DAY]]}
        at = self.at([(0, 509), (95 * DAY, 535), (195 * DAY, 535)])
        self.assertEqual(eb.chapter_banners(runs, {509: 535}, at, EVERY), {"509": [509, None, None]})

    def test_a_banner_missing_from_any_language_is_not_recorded(self):
        paths = EVERY - {"ui)quest)ja)banner)event_banner_509"}
        runs = {"509": [[0, 20 * DAY], [100 * DAY, 120 * DAY]]}
        self.assertEqual(eb.chapter_banners(runs, {509: 535}, self.at([(0, 509), (95 * DAY, 535)]), paths), {})

    def test_a_chapter_the_final_data_lacks_is_left_out(self):
        self.assertEqual(eb.chapter_banners({"777": [[0, DAY]]}, {509: 535}, lambda t: {777: 1}, EVERY), {})


class Home(unittest.TestCase):
    def test_a_reused_row_gets_its_first_runs_event_image(self):
        at = lambda t: {50: "event_mom_banner_510" if t < 100 * DAY else "mission_mom_banner_911"}
        out = eb.home_rows({"50": [[200 * DAY, 210 * DAY], [0, 20 * DAY]]}, {50: "mission_mom_banner_911"}, at, EVERY)
        self.assertEqual(out, {"50": "event_mom_banner_510"})

    def test_only_event_images_the_game_files_have(self):
        at = lambda t: {50: "event_mom_banner_999", 60: "limited_03"}
        out = eb.home_rows({"50": [[0, DAY]], "60": [[0, DAY]]}, {50: "x", 60: "y"}, at, EVERY)
        self.assertEqual(out, {})

    def test_rows_the_calendar_leaves_parked_are_skipped(self):
        at = lambda t: {50: "event_mom_banner_510"}
        self.assertEqual(eb.home_rows({"50": [[0, DAY]]}, {50: "x"}, at, EVERY, unrestored={50}), {})


class Recreated(unittest.TestCase):
    def test_garden_of_benedictions_first_run_shows_banner_900(self):
        # 512 was redrawn for the 2022 rerun; Bunker's server builds 900 (translation/banners.go).
        self.assertEqual(eb.with_recreated({"512": [512, 512, None], "509": [509, None]}),
                         {"512": [900, 512, None], "509": [509, None]})

    def test_a_chapter_with_no_other_change_gets_the_recreated_run(self):
        self.assertEqual(eb.with_recreated({}), {"512": [900]})


class Notices(unittest.TestCase):
    """A home banner whose notice the pack lacks opens a notice rebuilt for it."""
    # MomBannerId -> (DestinationDomainType, DestinationDomainId, StartDatetime)
    FINAL = {2: (23, 156, 4_000_000_000_000), 3: (23, 1057, 1), 4: (1, 156, 1), 5: (23, 12, 4_000_000_000_000), 6: (23, 7, 1)}

    def test_restored_or_dated_rows_with_a_missing_notice(self):
        out = eb.home_notices(self.FINAL, {"2": [[0, DAY]]}, pack_ids={1057})
        self.assertEqual(out, {"2": eb.NOTICE_BASE + 2, "6": eb.NOTICE_BASE + 6})  # 5 stays parked; 4 opens no notice

    def test_rows_the_calendar_leaves_parked_are_skipped(self):
        self.assertEqual(eb.home_notices(self.FINAL, {"2": [[0, DAY]]}, pack_ids={1057}, unrestored={2}), {"6": eb.NOTICE_BASE + 6})


class Pick(unittest.TestCase):
    def test_the_newest_master_before_the_time(self):
        self.assertEqual(eb.pick([10, 20, 30], 25), 20)

    def test_the_middle_of_a_long_run_is_within_its_first_month(self):
        self.assertEqual(eb.middle(0, 400 * DAY), 15 * DAY)


if __name__ == "__main__":
    unittest.main()
