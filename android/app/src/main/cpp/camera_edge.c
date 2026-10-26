// Story rooms: the camera stops at the room's edge where the invisible walls do.
//
// In story rooms the walls at the screen's sides (ScreenEdgeWallController)
// sit at the camera's x plus orthographicSize × the screen's aspect ratio,
// capped at the iPhone X's 19.5:9: on a wider screen the game shows black bars
// and keeps the play area 19.5:9. The camera that follows the player
// (CameraObjectWithFollowCurrentActor.Clamp) keeps itself inside the room using
// Screen.width / Screen.height instead, uncapped. On a screen wider than 19.5:9
// (a 2.4:1 phone with "Full screen, around the camera") it stops short of the
// room's end, the wall stops the player the same distance short, and a story
// trigger in that strip can't be reached: the scene doesn't go on (chapter 4,
// "A Tool of the Master", at the right of the room).
//
// Clamp's half width becomes orthographicSize × CalculatorCamera.
// GetCurrentAspectRatioWithoutBlackBelt(), the game's own capped ratio (the
// same 19.5:9 constant the walls use):
//
//     bl Screen.get_width -> bl GetCurrentAspectRatioWithoutBlackBelt
//     mov w20, w0          -> fmul s0, s9, s0     (s9 holds orthographicSize)
//     mov x0, xzr          -> b <the clamp>
//
// x0 is already 0 (the method argument) from the instruction before, and s9
// survives the call (d8-d15 are callee-saved). RVAs from the 3.7.1 ARM64
// game's IL2CPP metadata. Every word is checked first; on any unknown
// instruction nothing is changed.
#include "camera_edge.h"

static const struct { uint32_t rva, original, patched; } kSites[] = {
    {0x3808EDC, 0x9455bba7u, 0x97bda3bdu},  // bl Screen.get_width -> bl GetCurrentAspectRatioWithoutBlackBelt (0x2771DD0)
    {0x3808EE0, 0x2a0003f4u, 0x1e200920u},  // mov w20, w0 -> fmul s0, s9, s0
    {0x3808EE4, 0xaa1f03e0u, 0x14000006u},  // mov x0, xzr -> b 0x3808EFC (the clamp)
};

int camera_edge_fix(uint8_t *base, int (*write_word)(uint32_t *address, uint32_t value)) {
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
