#include "bunker_button_layout.h"

float bunker_row_gap(float available, float button_width, int buttons, float gap, float min_gap) {
    if (buttons < 2) return gap;
    float fits = (available - button_width * (float)buttons) / (float)(buttons - 1);
    if (fits >= gap) return gap;
    return fits > min_gap ? fits : min_gap;
}

int bunker_tap_allowed(int neighbour_enabled, int row_has_tap_event) {
    return neighbour_enabled && row_has_tap_event;
}
