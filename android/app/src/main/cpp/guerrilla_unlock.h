// The guerrilla quests' Force Unlock button (guerrilla_unlock.c).
#pragma once
#include <stdint.h>

/** Hides the Force Unlock button while the game data has no unlock valid now. Returns 0, or -1 if the library is unknown or can't be written. */
int guerrilla_unlock_button(uint8_t *base, int (*hook)(uint32_t *at, const uint32_t original[4], void (*target)(void)));
