// Flying Mama's game logic at 30 steps a second above 30 fps (flying_mom.c).
#pragma once

#include <stdint.h>

/** Loads the IL2CPP API through resolve ("il2cpp_domain_get", ...); log gets progress. Returns 0 or -1. */
int flying_mom_init(void *(*resolve)(const char *name), void (*log)(const char *message));

/**
 * Points FlyingMomPresenter.Update and Time.deltaTime at flying_mom.c. Call on
 * Unity's main thread once the game's code has loaded. Returns 1 when done, 0
 * while IL2CPP isn't up yet (try again later), below 0 if it can't (-2 classes
 * or methods missing, -3 Time.deltaTime not the expected internal call).
 */
int flying_mom_route(void);

/** When the minigame's logic runs: an accumulator of 30 Hz steps, for flying_mom.c and its tests. Starts zeroed. */
typedef struct {
    double due;       // steps owed; one runs when this reaches about 1
    float time;       // game time (Time.deltaTime) since the last step
    float step_time;  // game time the step that runs now covers
    int started;      // the first frame is a step
} FlyingMomClock;

/** Adds a frame; returns 1 when a step runs this frame (always on a touch that began this frame). */
int flying_mom_clock_tick(FlyingMomClock *clock, float unscaled_delta, float delta, int touch_began);

/**
 * The address of the code pointer an IL2CPP internal-call wrapper caches ("adrp xN; ldr x0, [xN, #off]"
 * in its first instructions), with code mapped at address; 0 if it isn't one.
 */
uintptr_t flying_mom_icall_slot(const uint32_t *code, uintptr_t address);
