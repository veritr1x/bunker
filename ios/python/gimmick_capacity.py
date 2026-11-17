"""The world map holds 4096 rows of each gimmick table on iOS too.

WorldMapGimmickModel keeps its gimmick tables (ornaments, sequences, schedules,
gimmicks, ...) in arrays of a fixed size, 1024, set in its static constructor.
Schedules are kept from the first one that hasn't ended, so the Original
calendar, which moves the game's 2021-2024 schedules into the coming years,
gives it 1638 at once. The 1025th fails to load, the map then follows a gimmick
chain to "not found" (-1), and opening the map hangs the game.

On iOS the constructor writes the sizes four at a time from one vector, which
becomes 4096 in each lane:

    movi v1.4s, #0x4, lsl #8 -> movi v1.4s, #0x10, lsl #8

Same change as the Android build (android/app/src/main/cpp/gimmick_capacity.c).
File offset in the 3.7.1 UnityFramework (WorldMapGimmickModel..cctor, from its
IL2CPP metadata); applied with text_buffer.patch_text_buffer.
"""

SITES = (
    (0x281F924, 0x4F002481, 0x4F002601),  # movi v1.4s, #0x4, lsl #8 -> #0x10, lsl #8
)
