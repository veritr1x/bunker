// How often the campaign badges redraw their remaining time (badge_pace.c).
#pragma once

#include <stdint.h>

/**
 * Loads the IL2CPP API through resolve ("il2cpp_domain_get", ...) and, once the
 * game has started, takes over CampaignSingleBadge.Update so each badge sets its
 * remaining time once a second instead of every frame. Returns 0, or -1 if the
 * API is missing.
 */
int badge_pace_init(void *(*resolve)(const char *name), void (*log)(const char *message));

/** The table badge_pace.c keeps, for its tests. */
#define BADGE_PACE_SLOTS 256
typedef struct {
    void *self[BADGE_PACE_SLOTS], *label[BADGE_PACE_SLOTS];
    int64_t second[BADGE_PACE_SLOTS];
} BadgePace;

/**
 * 1 when the badge should update now (its first call, or the first in a new
 * second), and records it. A badge is known by its address and its label: a
 * new badge made where a destroyed one was has a new label, so its first call
 * updates it.
 */
int badge_pace_due(BadgePace *pace, void *self, void *label, int64_t second);
