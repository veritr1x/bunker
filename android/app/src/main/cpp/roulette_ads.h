// The Special Gift Roulette without its video ad (roulette_ads.c).
#pragma once

/**
 * Loads the IL2CPP API through resolve ("il2cpp_domain_get", ...); log gets progress.
 * unity_send_message is iOS's UnitySendMessage (NULL on Android). Returns 0 or -1.
 */
int roulette_ads_init(void *(*resolve)(const char *name), void (*log)(const char *message),
                      void (*unity_send_message)(const char *object, const char *method, const char *argument));

/** Stands in for showing a rewarded video: raises "ad rewarded" and "ad closed". */
void roulette_ads_show(void *self, void *method);

/**
 * Points the ironSource agent's showRewardedVideo at roulette_ads_show. Returns 1
 * when done, 0 while the agent doesn't exist yet (try again later), below 0 if it can't
 * (-2 no IronSource fields, -3 no showRewardedVideo, -4 not in the method table).
 */
int roulette_ads_route_agent(void);
