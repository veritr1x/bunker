// Arena battle mods: No death, One hit and Zero cooldown, applied live in
// Arena battles, for Android and iOS (the iOS launcher builds this file too).
#ifndef BATTLE_MODS_H
#define BATTLE_MODS_H

#include "battle_mods_settings.h"

/** Loads the settings and hooks the battle HUD once IL2CPP is up (on a thread); 0, or -1 when the API is missing. */
int battle_mods_init(void *(*resolve)(const char *name), void (*log)(const char *message), const char *settings_path);
BattleMods battle_mods_get(void);
/** Applies from the next frame and saves the settings file. Main thread. */
void battle_mods_set(BattleMods mods);
/** The live battle's BattleContext (held by the engine), or NULL. */
void *battle_mods_context(void);
/** 1 while an Arena battle runs and the mods can reach it. */
int battle_mods_in_arena(void);
/** Called each battle frame after the mods (battle_mods_ui.c), with the HUD's BattleSystemMenuPresenter. */
void battle_mods_set_hud_hook(void (*hud)(void *presenter));

/** The button and popup (battle_mods_ui.c); after battle_mods_init. 0, or -1 when the API is missing. */
int battle_mods_ui_init(void *(*resolve)(const char *name), void (*log)(const char *message));

#endif
