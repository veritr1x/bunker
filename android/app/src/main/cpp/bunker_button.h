// The in-game Bunker button (bunker_button.c), for Android and iOS.
#pragma once

// resolve finds IL2CPP's exported functions by name, log reports problems and
// open brings up the Bunker launcher (called on Unity's thread). Returns 0
// when the button will be added once the game has started, -1 when IL2CPP's
// API is missing (the game then runs as it was).
int bunker_button_init(void *(*resolve)(const char *name), void (*log)(const char *message), void (*open)(void));
