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


E = cal.Entry
ART = "ui/gacha/en/limited_46/mom_banner.assetbundle"


class Timeline(unittest.TestCase):
    def setUp(self):
        self.state = {"loop": 1, "loopStart": cal.LAUNCH + 200 * WEEK}
        self.now = self.state["loopStart"] + 20 * WEEK

    def items(self):
        n = self.now
        return [E("arena", "Season 1", n - 3 * DAY, n + 20 * DAY),
                E("summon", "Vol. 2", n - 5 * DAY, n + 25 * DAY, "/schedule/summon/46", ART),
                E("summon", "Gone", n - 30 * DAY, n - 8 * DAY, "/schedule/summon/45"),
                E("summon", None, n + 10 * DAY, n + 40 * DAY, "/schedule/summon/50"),
                E("event", "Far off", n + 93 * DAY, n + 100 * DAY),
                E("shop", "Medal Exchange", n - 400 * DAY, n + 600 * DAY),
                E("event", "Cage", n - 2 * DAY, n + 2 * DAY, "/schedule/event/120"),
                E("pass", "Mission pass, month 1", n - DAY, n + DAY),
                E("hunt", "Subjugation Battle 1", n - DAY, n + DAY)]

    def test_window_is_a_week_back_and_three_months_ahead(self):
        t = cal.timeline(self.state, [], self.now)
        self.assertEqual((t["now"], t["from"], t["to"]), (self.now, self.now - 7 * DAY, self.now + 92 * DAY))

    def test_window_stops_at_loop_end(self):
        now = cal.loop_end(self.state) - 10 * DAY
        self.assertEqual(cal.timeline(self.state, [], now)["to"], cal.loop_end(self.state))

    def test_only_items_in_the_window_and_kinds_in_order(self):
        rows = cal.timeline(self.state, self.items(), self.now)["rows"]
        self.assertEqual([(r["kind"], r["label"]) for r in rows],
                         [("summon", "Summons"), ("event", "Events"), ("shop", "Shops"), ("arena", "Arena")])
        names = [i["name"] for r in rows for i in r["items"]]
        self.assertEqual(sorted(names), sorted(["Vol. 2", "Summon", "Cage", "Medal Exchange", "Season 1"]))

    def test_long_bar_keeps_its_dates(self):
        [shop] = cal.timeline(self.state, self.items(), self.now)["rows"][2]["items"]
        self.assertEqual((shop["start"], shop["end"]), (self.now - 400 * DAY, self.now + 600 * DAY))

    def test_soon_is_open_items_ending_within_a_week_soonest_first(self):
        n = self.now
        items = [E("event", "B", n - DAY, n + 7 * DAY - 1), E("event", "A", n - DAY, n + 2 * DAY),
                 E("event", "Later", n - DAY, n + 8 * DAY), E("event", "Upcoming", n + DAY, n + 3 * DAY)]
        self.assertEqual([i["name"] for i in cal.timeline(self.state, items, n)["soon"]], ["A", "B"])

    def test_original_dates_move_everything(self):
        plain = cal.timeline(self.state, self.items(), self.now)
        shift = self.state["loopStart"] - cal.LAUNCH
        moved = cal.timeline(dict(self.state, originalDates=True), self.items(), self.now)
        self.assertEqual((moved["now"], moved["from"], moved["to"]), (plain["now"] - shift, plain["from"] - shift, plain["to"] - shift))
        for a, b in zip([i for r in plain["rows"] for i in r["items"]] + plain["soon"],
                        [i for r in moved["rows"] for i in r["items"]] + moved["soon"]):
            self.assertEqual((b["start"], b["end"]), (a["start"] - shift, a["end"] - shift))

    def test_unnamed_items_take_their_kind(self):
        summons = cal.timeline(self.state, self.items(), self.now)["rows"][0]["items"]
        self.assertIn("Summon", [i["name"] for i in summons])

    def test_art_is_a_pod_programs_url(self):
        summons = cal.timeline(self.state, self.items(), self.now)["rows"][0]["items"]
        vol2 = next(i for i in summons if i["name"] == "Vol. 2")
        self.assertEqual((vol2["art"], vol2["ref"]), ("/patcher/calendar/art?path=" + ART, "/schedule/summon/46"))
        self.assertEqual(next(i for i in summons if i["name"] == "Summon")["art"], "")


if __name__ == "__main__":
    unittest.main()
