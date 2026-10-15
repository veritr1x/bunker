// The game's text builder (Applibot.Text.ArtStringBuilder) writes formatted
// text straight into its char buffer. Before each write it checks the space:
//
//     if (position + needed > buffer.Length) Array.Resize(ref buffer, buffer.Length * 2);
//
// It doubles only once, so text more than twice the buffer's size runs past
// its end into whatever object follows. The summon confirmation (about 170
// characters, "...Available for purchase until {0}.") does this soon after
// the game starts, while the builders are still small; it overwrote one of the
// cached game texts, and the next asset unload (Unity's liveness walk) crashed
// on it (SIGSEGV in libil2cpp+0x257DA0C, fault address made of text).
//
// Every one of these checks (58, most inlined into AppendArguments and
// AppendBlock) now grows to buffer.Length + position + needed, which always
// fits: "lsl w1, wLen, #1" becomes "add w1, wLen, wNeeded". In CheckCapacity
// and CachedOrGenerateBuilder the needed-size register is reused for the
// method address, so the add goes first and the adrp/ldr pair moves down one.
//
// RVAs from the 3.7.1 ARM64 game's IL2CPP metadata. Every word is checked first;
// on any unknown instruction nothing is changed.
#include "text_buffer.h"

static const struct { uint32_t rva, original, patched; } kSites[] = {
    {0x38B1744, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument1<bool>>
    {0x38B18F0, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument1<short>>
    {0x38B1A9C, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument1<int>>
    {0x38B1C48, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument1<long>>
    {0x38B1DF4, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument1<object>>
    {0x38B1FA0, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument1<float>>
    {0x38B214C, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument2<short, byte>>
    {0x38B22F8, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument2<int, bool>>
    {0x38B24A4, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument2<int, int>>
    {0x38B2650, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument2<int, object>>
    {0x38B27FC, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument2<object, int>>
    {0x38B29A8, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument2<object, object>>
    {0x38B2B54, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument3<int, int, int>>
    {0x38B2D00, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument3<int, object, object>>
    {0x38B2EAC, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument3<object, int, int>>
    {0x38B3058, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument3<object, int, object>>
    {0x38B3204, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument3<object, object, int>>
    {0x38B33B0, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument3<object, object, object>>
    {0x38B355C, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument4<int, int, int, int>>
    {0x38B3708, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument4<int, int, object, object>>
    {0x38B38B4, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument4<object, int, int, int>>
    {0x38B3A60, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument4<object, int, object, int>>
    {0x38B3C0C, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument4<object, object, object, int>>
    {0x38B3DB8, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument4<object, object, object, object>>
    {0x38B3F64, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument6<object, int, object, int, object, int>>
    {0x38B4110, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<Argument6<object, object, object, object, object, object>>
    {0x38B42BC, 0x531f7941u, 0x0b0b0141u},  // AppendArguments<object>
    {0x3BF8AA0, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument4<int, int, int, int>>
    {0x3BF9624, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument4<int, int, object, object>>
    {0x3BFA1A8, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument4<object, int, int, int>>
    {0x3BFAD10, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument4<object, int, object, int>>
    {0x3BFB878, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument4<object, object, object, int>>
    {0x3BFC3E0, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument4<object, object, object, object>>
    {0x3BFCF70, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument6<object, int, object, int, object, int>>
    {0x3BFDB00, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument6<object, object, object, object, object, object>>
    {0x3BFE594, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<object>
    {0x4BD1600, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument1<bool>>
    {0x4BD2144, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument1<short>>
    {0x4BD2C88, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument1<int>>
    {0x4BD37CC, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument1<long>>
    {0x4BD4310, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument1<object>>
    {0x4BD4E54, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument1<float>>
    {0x4BD5998, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument2<short, byte>>
    {0x4BD64DC, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument2<int, bool>>
    {0x4BD7020, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument2<int, int>>
    {0x4BD7B7C, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument2<int, object>>
    {0x4BD86D8, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument2<object, int>>
    {0x4BD9234, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument2<object, object>>
    {0x4BD9DB8, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument3<int, int, int>>
    {0x4BDA93C, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument3<int, object, object>>
    {0x4BDB498, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument3<object, int, int>>
    {0x4BDC01C, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument3<object, int, object>>
    {0x4BDCBA0, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument3<object, object, int>>
    {0x4BDD724, 0x531f7921u, 0x0b0a0121u},  // AppendBlock<Argument3<object, object, object>>
    {0x53B53B4, 0x531f7941u, 0x0b0b0141u},  // Append
    {0x53B5648, 0x531f7941u, 0x0b0b0141u},  // Append
    {0x53B5C90, 0x9000f989u, 0x0b090101u},  // CheckCapacity
    {0x53B5C94, 0xf9470529u, 0x9000f989u},  // CheckCapacity
    {0x53B5C98, 0xa9427bfdu, 0xf9470529u},  // CheckCapacity
    {0x53B5C9C, 0xa9414ff4u, 0xa9427bfdu},  // CheckCapacity
    {0x53B5CA0, 0x531f7901u, 0xa9414ff4u},  // CheckCapacity
    {0x53B6064, 0xf000f969u, 0x0b090101u},  // CachedOrGenerateBuilder
    {0x53B6068, 0xf9470529u, 0xf000f969u},  // CachedOrGenerateBuilder
    {0x53B606C, 0x531f7901u, 0xf9470529u},  // CachedOrGenerateBuilder
};

int text_buffer_fix(uint8_t *base, int (*write_word)(uint32_t *address, uint32_t value)) {
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
