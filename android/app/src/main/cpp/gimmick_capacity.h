// The world map's gimmick tables (gimmick_capacity.c).
#pragma once
#include <stdint.h>

/** Lets the world map hold 4096 rows of each gimmick table instead of 1024. Returns 0, or -1 if the library is unknown or can't be written. */
int gimmick_capacity_raise(uint8_t *base, int (*write_word)(uint32_t *address, uint32_t value));
