// The Special Gift Roulette without its video ad (roulette_ads.c).
#pragma once

/** Loads the IL2CPP API through resolve ("il2cpp_domain_get", ...). Returns 0 or -1. */
int roulette_ads_init(void *(*resolve)(const char *name));

/** Stands in for showing a rewarded video: raises "ad rewarded" and "ad closed". */
void roulette_ads_show(void *self, void *method);

/**
 * Points the ironSource agent's showRewardedVideo at roulette_ads_show. Returns 1
 * when done, 0 while the agent doesn't exist yet (try again later), -1 if it can't.
 */
int roulette_ads_route_agent(void);
