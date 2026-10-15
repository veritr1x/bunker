// The game's text builder overrunning its buffer (text_buffer.c).
#pragma once
#include <stdint.h>

/** Fixes ArtStringBuilder's buffer growth in the loaded game library. Returns 0, or -1 if the library is unknown or can't be written. */
int text_buffer_fix(uint8_t *base, int (*write_word)(uint32_t *address, uint32_t value));
