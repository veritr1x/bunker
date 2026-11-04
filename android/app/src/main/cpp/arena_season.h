// Arena season dates for the season turns (arena_season.c).
#pragma once
#include <stdint.h>

/** Loads the IL2CPP API through resolve ("il2cpp_domain_get", ...); log gets the result. Returns 0 or -1. */
int arena_season_init(void *(*resolve)(const char *name), void (*log)(const char *message));

/** Gives the Arena seasons that take turns the dates of their turns. Call on Unity's main thread once the game's code has loaded. */
void arena_season_dates(void);

/** The turn dates for the seasons in rows at now (the server's pvp.Catalog.Season rule); exposed for tests. Fills start and end
 *  per row (unchanged rows keep theirs) and returns how many rows changed. */
typedef struct { int32_t id; int64_t start, end; int32_t grade, season_rank, weekly_rank; int invalid; } ArenaSeasonRow;
int arena_season_turns(const ArenaSeasonRow *rows, int count, int64_t now, int64_t *start, int64_t *end);
