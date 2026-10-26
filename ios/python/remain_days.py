"""Remaining times stop at 999 days on iOS too.

Times more than a few days off show as "{0}d"
(CalculatorDateTime.GetRemainTimeString(int days)). Campaigns left open to
31 December 2099 are 26,000 days away, and the campaign badges' small box draws
"26731d" as an overlapping jumble. In both callers the class-initialised check
just before the call (it already is) becomes the cap:

    mov w8, #999 / cmp w0, w8 / csel w0, w0, w8, le / b <the call>

Same change as the Android build (android/app/src/main/cpp/remain_days.c).
File offsets in the 3.7.1 UnityFramework; applied with text_buffer.patch_text_buffer.
"""

SITES = (
    (0x24BD35C, 0xAA0003F3, 0x52807CE8),  # GetRemainTimeString: mov x19, x0 -> mov w8, #999
    (0x24BD360, 0xF94002C0, 0x6B08001F),  # ldr x0, [x22] -> cmp w0, w8
    (0x24BD364, 0x79425C08, 0x1A88D000),  # ldrh w8, [x0, #0x12e] -> csel w0, w0, w8, le
    (0x24BD368, 0x36480088, 0x14000005),  # tbz w8, #9 -> b 0x24BD37C (the call)
    (0x24BD5B8, 0xAA0003F3, 0x52807CE8),  # GetRemainDigitalTimeString: the same
    (0x24BD5BC, 0xF94002C0, 0x6B08001F),
    (0x24BD5C0, 0x79425C08, 0x1A88D000),
    (0x24BD5C4, 0x36480088, 0x14000005),  # -> b 0x24BD5D8 (the call)
)
