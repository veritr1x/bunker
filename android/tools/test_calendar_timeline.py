#!/usr/bin/env python3
"""The Schedule page's timeline (android_calendar.py): what each entry links to
and shows, with small game tables. Needs the Android Python requirements."""
from pathlib import Path
import sys, unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "android/app/src/main/python"))
import android_calendar as cal  # noqa: E402

DAY, WEEK = cal.DAY, cal.WEEK
T0 = cal.LAUNCH + 10 * WEEK  # a date inside the service

TABLES = {
    "EventQuestChapter": [
        {"EventQuestChapterId": 120, "StartDatetime": T0, "EndDatetime": T0 + 14 * DAY, "BannerAssetId": 5},
        {"EventQuestChapterId": 120 + cal.COPY_STEP, "StartDatetime": T0 + 30 * DAY, "EndDatetime": T0 + 44 * DAY, "BannerAssetId": 5},
        {"EventQuestChapterId": 130, "StartDatetime": T0, "EndDatetime": T0 + 7 * DAY, "BannerAssetId": 0},
    ],
    "GachaMedal": [{"ShopTransitionGachaId": 46, "ConsumableItemId": 9001, "AutoConvertDatetime": T0 + 60 * DAY}],
    "MomBanner": [{"MomBannerId": 1, "DestinationDomainType": 1, "DestinationDomainId": 46, "BannerAssetName": "limited_46",
                   "StartDatetime": T0, "EndDatetime": T0 + 40 * DAY}],
    "Shop": [{"ShopId": 7, "ShopGroupType": 4, "StartDatetime": T0, "EndDatetime": T0 + 90 * DAY}],
    "PvpSeason": [{"PvpSeasonId": 202001, "SeasonStartDatetime": T0, "SeasonEndDatetime": T0 + 28 * DAY}],
}


class Entries(unittest.TestCase):
    def setUp(self):
        self.patches = [mock.patch.object(cal, "table", lambda name: TABLES.get(name, [])),
                        mock.patch.object(cal, "names", lambda kind: {}),
                        mock.patch.object(cal, "history", lambda: {}),
                        mock.patch.object(cal, "shop_opens_by_price", lambda: {})]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def of(self, kind):
        return [e for e in cal.entries() if e.kind == kind]

    def test_summon_links_to_its_archive_page_with_its_banner(self):
        [summon] = self.of("summon")
        self.assertEqual((summon.ref, summon.art), ("/schedule/summon/46", "ui/gacha/en/limited_46/mom_banner.assetbundle"))

    def test_event_rerun_links_to_the_original_chapter(self):
        runs = [e for e in self.of("event") if e.ref == "/schedule/event/120"]
        self.assertEqual(len(runs), 2)
        self.assertTrue(all(e.art == "ui/quest/en/banner/event_banner_005.assetbundle" for e in runs))

    def test_event_without_banner_has_no_art(self):
        [event] = [e for e in self.of("event") if e.ref == "/schedule/event/130"]
        self.assertEqual(event.art, "")

    def test_shops_and_arena_have_no_link_or_art(self):
        others = self.of("shop") + self.of("arena")
        self.assertEqual(len(others), 2)
        self.assertTrue(all((e.ref, e.art) == ("", "") for e in others))

    def test_entries_still_unpack_as_four_fields_first(self):
        kind, name, start, end, *_ = self.of("arena")[0]
        self.assertEqual((kind, start, end), ("arena", T0, T0 + 28 * DAY))


if __name__ == "__main__":
    unittest.main()
