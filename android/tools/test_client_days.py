#!/usr/bin/env python3
"""The game's own day markers, cleared when Pod Programs moves the game's clock
back: the same keys in both launchers."""
from pathlib import Path
import re, unittest

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


if __name__ == "__main__":
    unittest.main()
