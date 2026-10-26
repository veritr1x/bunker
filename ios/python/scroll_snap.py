"""Snapping lists (the summon banners) arrive at their row on iOS too.

DarkScrollRect.UpdateSnapPosition eases a list to the chosen row with
SmoothDamp and counts it as there within 0.01 (kScrollBorder). Above 30 fps
each frame's step is so small that, far down a long list, it is below the
position's float precision: the list stops just short, keeps a small speed,
and IsScrolling stays true, so the Summon buttons ignore taps. The load of
the 0.01 limit becomes "fmov s1, #1.0" (1 unit, invisible). Same change as
the Android build (android/app/src/main/cpp/display_patch.c, kSnapArrive).

File offset in the 3.7.1 UnityFramework; applied with text_buffer.patch_text_buffer.
"""

SITES = (
    (0x22E09B0, 0xBD401901, 0x1E2E1001),  # UpdateSnapPosition: ldr s1, [x8, #0x18] -> fmov s1, #1.0
)
