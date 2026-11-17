// The world map keeps each gimmick table (ornaments, sequences, schedules,
// gimmicks, user progress, ...) in an array of WorldMapGimmickModel's fixed
// size, 1024, set in its static constructor. Schedules are kept from the
// first one that hasn't ended, so the Original calendar, which moves the
// game's 2021-2024 schedules into the coming years, gives it 1638 at once (of
// 1903). The 1025th fails to load, and the map then follows a gimmick chain
// to "not found" (-1), which GenerateWorldMapGimmickOutGameAsync never
// treats as its end: opening the map hangs the game.
//
// The constructor sets all those sizes from one register; it becomes 4096:
//
//     orr w10, wzr, #0x400 -> orr w10, wzr, #0x1000
//
// RVA from the 3.7.1 ARM64 game's IL2CPP metadata (WorldMapGimmickModel..cctor).
// The word is checked first; on any other instruction nothing is changed.
#include "gimmick_capacity.h"
#include "game_region.h"

static const struct { uint32_t rva, original, patched; } kSite = {0x2D3FFCC, 0x321603eau, 0x321403eau};

int gimmick_capacity_raise(uint8_t *base, int (*write_word)(uint32_t *address, uint32_t value)) {
    uint32_t *address = (uint32_t *)(base + game_rva(kSite.rva));
    if (*address == kSite.patched) return 0;
    if (*address != kSite.original) return -1;
    return write_word(address, kSite.patched) ? -1 : 0;
}
