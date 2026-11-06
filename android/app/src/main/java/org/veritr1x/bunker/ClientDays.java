package org.veritr1x.bunker;

/**
 * The game keeps its own day and time markers in its PlayerPrefs, outside the
 * save: the last day it showed the roulette's FREE badge, the login bonus, a
 * promotion, and so on. It compares them with the server's clock, and only a
 * later day counts as a new one. Pod Programs can move that clock back (the
 * calendar turned off after a jump, "Show original dates", a new loop with it):
 * a 2028 marker then hides the FREE badge until 2028. Pod Programs leaves
 * RESET_FILE beside the save then, closing the game if it runs (the game also
 * keeps them in memory), and the markers are cleared before it starts again
 * (GameProcessProvider). The game then treats the day as a new one.
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

    /** android_calendar.client_days_file. */
    static final String RESET_FILE = "client-days.reset";

    private ClientDays() {}
}
