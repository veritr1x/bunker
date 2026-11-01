#!/usr/bin/env python3
"""The game's own day markers, cleared when "Show original dates" changes.

The Java test needs a JDK (javac and java on PATH).
"""
from pathlib import Path
import re, shutil, subprocess, tempfile, unittest

root = Path(__file__).resolve().parents[2]
JAVA = root / "android/app/src/main/java/org/veritr1x/bunker/ClientDays.java"
IOS = root / "ios/launcher/LunarLauncher.m"

# The day and time markers the game keeps in its PlayerPrefs (key names from
# the 3.7.1 game code).
MARKERS = {
    "login_bonus_spanning_day_key", "roulette_badge_spanning_day_key",
    "mom_promotion_spanning_day_key", "function_promotion_spanning_day_key",
    "mom_promotion_day_play_count_key", "function_promotion_day_play_count_key",
    "gacha_day_first_draw_unix_time_key", "gacha_draw_count_key",
    "last_opened_shop_unix_time_key", "last_display_tip_unix_time_key",
    "last_display_tip_background_unix_time_key", "daily_quest_message_lottery_unix_time_key",
    "world_map_notification_view_unix_time_key", "unknown_location_entry_unix_time_key",
    "last_limited_open_notification_unix_time",
}


def keys(source, start, end):
    block = source[source.index(start):]
    return set(re.findall(r'"([a-z_]+)"', block[:block.index(end)]))


class Keys(unittest.TestCase):
    def test_android_clears_every_marker(self):
        self.assertEqual(keys(JAVA.read_text(), "KEYS = {", "};"), MARKERS)

    def test_ios_clears_the_same_markers(self):
        self.assertEqual(keys(IOS.read_text(), "kClientDayKeys[] = {", "};"), MARKERS)


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "needs a JDK")
class Mode(unittest.TestCase):
    CASES = {
        "": False,
        '{"loop": 1, "loopStart": 1793152800000}': False,
        '{\n  "loopStart": 1793152800000,\n  "originalDates": false\n}': False,
        '{\n  "loopStart": 1793152800000,\n  "originalDates": true\n}': True,
        '{"loopStart":1793152800000,"originalDates":true}': True,
    }

    def test_original_dates_read_from_calendar_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "Main.java"
            # Each argument is a calendar.json text; "-" stands for no file.
            main.write_text("package org.veritr1x.bunker;\npublic class Main { public static void main(String[] args) {\n"
                            "for (String a : args) System.out.println(ClientDays.originalDates(a.equals(\"-\") ? null : a));\n"
                            "} }\n")
            subprocess.run(["javac", "-d", tmp, str(JAVA), str(main)], check=True)
            out = subprocess.run(["java", "-cp", tmp, "org.veritr1x.bunker.Main", *self.CASES, "-"], check=True, capture_output=True, text=True).stdout.split()
        self.assertEqual(out, [str(v).lower() for v in self.CASES.values()] + ["false"])


if __name__ == "__main__":
    unittest.main()
