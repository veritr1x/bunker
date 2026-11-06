// Back to the title screen at once after a change in Pod Programs (title_now.c).
#pragma once

/**
 * Loads the IL2CPP API through resolve ("il2cpp_domain_get", ...) and names
 * the marker file Lunar Tear writes when the game should go back to its title
 * screen (interceptor.RequestTitle). Returns 0, or -1 if the API is missing.
 */
int title_now_init(void *(*resolve)(const char *name), void (*log)(const char *message), const char *marker);

/** On Unity's main thread, each frame a header updates (bunker_button.c). */
void title_now_tick(void);
