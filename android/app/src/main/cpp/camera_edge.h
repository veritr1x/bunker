// Story rooms' camera edge (camera_edge.c).
#pragma once
#include <stdint.h>

/** Makes the story camera stop where the screen-edge walls do on screens wider than 19.5:9. Returns 0, or -1 if the library is unknown or can't be written. */
int camera_edge_fix(uint8_t *base, int (*write_word)(uint32_t *address, uint32_t value));
