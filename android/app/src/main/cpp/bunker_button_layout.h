// The in-game Bunker button's rules (bunker_button.c), kept apart so they can
// be tested on a computer (android/tools/test_bunker_button.py).
#pragma once

// The gap between the top row's buttons so that `buttons` of `button_width`
// fit in `available`: `gap` when they already fit, otherwise the largest gap
// that fits, but never less than `min_gap` (the game's own buttons keep their
// size).
float bunker_row_gap(float available, float button_width, int buttons, float gap, float min_gap);

// The Bunker button opens the launcher only while the game lets the row be
// tapped: its neighbour is enabled and the row has its tap events.
int bunker_tap_allowed(int neighbour_enabled, int row_has_tap_event);
