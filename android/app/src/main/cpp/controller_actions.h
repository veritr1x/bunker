#pragma once
// Input arrives on the platform UI thread. Dispatch game actions in EventSystem.Update.
enum { BUNKER_PAD_CLEAR, BUNKER_PAD_SKIP, BUNKER_PAD_BACK };
void bunker_pad_request(int action);
void bunker_pad_prepare(void *(*resolve)(const char *));
void bunker_pad_install(void);
