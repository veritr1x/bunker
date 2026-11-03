// A name for Subjugation schedules without a season (big_hunt_season.c).
#pragma once

/** Loads the IL2CPP API through resolve ("il2cpp_domain_get", ...); log gets the result. Returns 0 or -1. */
int big_hunt_season_init(void *(*resolve)(const char *name), void (*log)(const char *message));

/** Gives season 0 the name "Subjugation Battles" if the game's texts lack it. Call on Unity's main thread once the game's code has loaded. */
void big_hunt_season_name(void);
