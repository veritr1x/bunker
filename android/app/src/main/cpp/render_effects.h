// The graphics effects turned off in Pod Programs › Display (render_effects.c).
#pragma once

#include <stddef.h>
#include <stdint.h>

/** Effects to turn off, as render_effects_init takes them. */
enum { RENDER_EFFECTS_SHADOWS = 1, RENDER_EFFECTS_REFLECTIONS = 2, RENDER_EFFECTS_BLOOM = 4 };

/** Loads the IL2CPP API through resolve; off is the effects to turn off (0: none). Returns 0 or -1. */
int render_effects_init(void *(*resolve)(const char *name), void (*log)(const char *message), int off);

/**
 * Turns the effects off in every performance preset and applies the current
 * preset again. Call on Unity's main thread once IL2CPP is up, each frame until
 * it returns non-zero: 1 done (or nothing to do), 0 the game isn't ready yet,
 * below 0 it can't (the game draws its effects).
 */
int render_effects_apply(void);

/** Clears the off effects' flags in count Config.LevelConfig entries (12 bytes each), for render_effects.c and its tests. */
void render_effects_clear(uint8_t *entries, size_t count, int off);
