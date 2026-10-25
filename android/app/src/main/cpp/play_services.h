// The game's Firebase start-up without Google Play services (play_services.c).
#pragma once
#include <stdint.h>

/** Makes Firebase's Play services check pass. Returns NULL, or why nothing changed. */
const char *play_services_fix(int (*write_word)(uint32_t *address, uint32_t value));
