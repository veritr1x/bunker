package org.veritr1x.bunker;

import java.util.regex.Pattern;

/**
 * The game keeps its own day and time markers in its PlayerPrefs, outside the
 * save: the last day it showed the roulette's FREE badge, the login bonus, a
 * promotion, and so on. It compares them with the server's clock, and only a
 * later day counts as a new one. "Show original dates" (Pod Programs › Content
 * › Schedule) moves that clock by years, so after a switch the markers are on
 * the wrong side of it: showing 2021, a 2026 marker hides the FREE badge for
 * the whole loop. The markers are cleared when the setting changes, before the
 * game starts; the game then treats the day as a new one.
 */
final class ClientDays {
    // Key names from the 3.7.1 game code (android/tools/test_client_days.py).
    // The iOS launcher clears the same keys (kClientDayKeys).
    static final String[] KEYS = {
        "login_bonus_spanning_day_key", "roulette_badge_spanning_day_key",
        "mom_promotion_spanning_day_key", "function_promotion_spanning_day_key",
        "mom_promotion_day_play_count_key", "function_promotion_day_play_count_key",
        "gacha_day_first_draw_unix_time_key", "gacha_draw_count_key",
        "last_opened_shop_unix_time_key", "last_display_tip_unix_time_key",
        "last_display_tip_background_unix_time_key", "daily_quest_message_lottery_unix_time_key",
        "world_map_notification_view_unix_time_key", "unknown_location_entry_unix_time_key",
        "last_limited_open_notification_unix_time",
    };

    private static final Pattern ON = Pattern.compile("\"originalDates\"\\s*:\\s*true");

    private ClientDays() {}

    /** True when calendar.json (null when there is none) has "Show original dates" on. */
    static boolean originalDates(String calendarJson) {
        return calendarJson != null && ON.matcher(calendarJson).find();
    }
}
