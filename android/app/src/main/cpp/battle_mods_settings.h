// Arena battle mods: the settings file and the rules the battle hook applies
// each frame (battle_mods.c). No game code here, so the host tests build it
// (android/tools/test_battle_mods.py).
#ifndef BATTLE_MODS_SETTINGS_H
#define BATTLE_MODS_SETTINGS_H

#include <stddef.h>

typedef struct { int no_death, one_hit, zero_cooldown; } BattleMods;

// No death raises the player's max and current HP to this; far below
// INT32_MAX, so the game's arithmetic cannot overflow.
#define BATTLE_MODS_HUGE_HP 1000000000
// The max HP of a team's filler slots (actors that are not characters).
#define BATTLE_MODS_FILLER_HP 1234567890

/** key=on|off lines (no_death, one_hit, zero_cooldown); anything else, or a value other than on, is off. */
void battle_mods_parse(const char *text, BattleMods *out);
/** The three lines, in that order; the length written, or -1 when buf is too small. */
int battle_mods_format(const BattleMods *mods, char *buf, size_t len);
/** All off and -1 when the file is missing or unreadable. */
int battle_mods_load(const char *path, BattleMods *out);
/** Written to path.tmp and renamed over path, so a cut write leaves the old file; 0 or -1. */
int battle_mods_save(const char *path, const BattleMods *mods);

int battle_mods_is_filler(int max_hp);
/** The player's max HP: huge while No death is on, else the character's own. */
int battle_mods_player_max(int no_death, int real_max);
/** The player's current HP: huge while No death is on; once off, no more than the character's own max. */
int battle_mods_player_hp(int no_death, int hp, int real_max);
/** An opponent's HP: held at 1 while One hit is on, so any hit defeats them. */
int battle_mods_opponent_hp(int one_hit, int hp);
/** A skill's cooldown, which counts up to max (ready): max while Zero cooldown is on. */
int battle_mods_cooltime(int zero_cooldown, int current, int max);

#endif
