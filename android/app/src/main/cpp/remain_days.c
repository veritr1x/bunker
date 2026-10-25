// Remaining times more than a few days off show as "{0}d"
// (CalculatorDateTime.GetRemainTimeString(int days)). Campaigns left open
// (31 December 2099) are 26,000 days away, and the campaign badges' small box
// draws "26731d" as an overlapping jumble. Both callers, GetRemainTimeString
// and GetRemainDigitalTimeString, pass at most 999 now.
//
// Each caller checks the class is initialised just before the call, which it
// already is (it has read its static fields). Those words become the cap:
//
//     mov w8, #999 / cmp w0, w8 / csel w0, w0, w8, le / b <the call>
//
// RVAs from the 3.7.1 ARM64 game's IL2CPP metadata. Every word is checked first;
// on any unknown instruction nothing is changed.
#include "remain_days.h"

static const struct { uint32_t rva, original, patched; } kSites[] = {
    {0x2967CE8, 0xf94002a8u, 0x52807ce8u},  // GetRemainTimeString: ldr x8, [x21] -> mov w8, #999
    {0x2967CEC, 0x2a0003f3u, 0x6b08001fu},  // mov w19, w0 -> cmp w0, w8
    {0x2967CF0, 0x3944bd09u, 0x1a88d000u},  // ldrb w9, [x8, #0x12f] -> csel w0, w0, w8, le
    {0x2967CF4, 0x360800a9u, 0x14000006u},  // tbz w9, #1 -> b 0x2967D0C (the call)
    {0x2967F54, 0xf94002a8u, 0x52807ce8u},  // GetRemainDigitalTimeString: the same
    {0x2967F58, 0x2a0003f3u, 0x6b08001fu},
    {0x2967F5C, 0x3944bd09u, 0x1a88d000u},
    {0x2967F60, 0x360800a9u, 0x14000006u},  // -> b 0x2967F78 (the call)
};

int remain_days_cap(uint8_t *base, int (*write_word)(uint32_t *address, uint32_t value)) {
    const int count = sizeof kSites / sizeof kSites[0];
    for (int i = 0; i < count; i++) {
        uint32_t now = *(uint32_t *)(base + kSites[i].rva);
        if (now != kSites[i].original && now != kSites[i].patched) return -1;
    }
    for (int i = 0; i < count; i++) {
        uint32_t *address = (uint32_t *)(base + kSites[i].rva);
        if (*address != kSites[i].patched && write_word(address, kSites[i].patched)) return -1;
    }
    return 0;
}
