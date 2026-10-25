// Remaining time shown in days (remain_days.c).
#pragma once
#include <stdint.h>

/** Caps the game's "{0}d" remaining time at 999 days in the loaded game library. Returns 0, or -1 if the library is unknown or can't be written. */
int remain_days_cap(uint8_t *base, int (*write_word)(uint32_t *address, uint32_t value));
