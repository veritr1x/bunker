// Japanese 3.7.1 RVAs resolved by method name AND full signature, then
// checked against both original binaries. See docs/ANDROID-REGIONS.md.
#ifndef BUNKER_GAME_REGION_H
#define BUNKER_GAME_REGION_H
#include <stdint.h>
extern int bunker_game_japanese;

static inline uint32_t game_rva(uint32_t global) {
    if (!bunker_game_japanese) return global;
    switch (global) {
    case 0x29420E8: return 0x2908D9C;
    case 0x2967CE8: return 0x2D31760;
    case 0x2967CEC: return 0x2D31764;
    case 0x2967CF0: return 0x2D31768;
    case 0x2967CF4: return 0x2D3176C;
    case 0x2967F54: return 0x2D319CC;
    case 0x2967F58: return 0x2D319D0;
    case 0x2967F5C: return 0x2D319D4;
    case 0x2967F60: return 0x2D319D8;
    case 0x2984210: return 0x29BB838;
    case 0x2984420: return 0x29BBA48;
    case 0x2A6530C: return 0x29AFF7C;
    case 0x2B01F88: return 0x2B5A870;
    case 0x2C7AC80: return 0x2C6E934;
    case 0x2C7ACD8: return 0x2C6E98C;
    case 0x2C7AD10: return 0x2C6E9C4;
    case 0x2D5F7A0: return 0x2D06248;
    case 0x2E5BE0C: return 0x2E5E8FC;
    case 0x2E5C31C: return 0x2E5EE0C;
    case 0x2EC1D04: return 0x31C09A0;
    case 0x30DF5A0: return 0x2CCAFD0;
    case 0x363082C: return 0x35659E4;
    case 0x37DC3D0: return 0x3762E14;
    case 0x3808EDC: return 0x37AA5F4;
    case 0x3808EE0: return 0x37AA5F8;
    case 0x3808EE4: return 0x37AA5FC;
    case 0x38B1744: return 0x3841A94;
    case 0x38B18F0: return 0x3841C40;
    case 0x38B1A9C: return 0x3841DEC;
    case 0x38B1C48: return 0x3841F98;
    case 0x38B1DF4: return 0x3842144;
    case 0x38B1FA0: return 0x38422F0;
    case 0x38B214C: return 0x384249C;
    case 0x38B22F8: return 0x3842648;
    case 0x38B24A4: return 0x38427F4;
    case 0x38B2650: return 0x38429A0;
    case 0x38B27FC: return 0x3842B4C;
    case 0x38B29A8: return 0x3842CF8;
    case 0x38B2B54: return 0x3842EA4;
    case 0x38B2D00: return 0x3843050;
    case 0x38B2EAC: return 0x38431FC;
    case 0x38B3058: return 0x38433A8;
    case 0x38B3204: return 0x3843554;
    case 0x38B33B0: return 0x3843700;
    case 0x38B355C: return 0x38438AC;
    case 0x38B3708: return 0x3843A58;
    case 0x38B38B4: return 0x3843C04;
    case 0x38B3A60: return 0x3843DB0;
    case 0x38B3C0C: return 0x3843F5C;
    case 0x38B3DB8: return 0x3844108;
    case 0x38B3F64: return 0x38442B4;
    case 0x38B4110: return 0x3844460;
    case 0x38B42BC: return 0x384460C;
    case 0x3A05C64: return 0x39A4044;
    case 0x3A0ECF8: return 0x39AD0D8;
    case 0x3BF8AA0: return 0x3B5CAAC;
    case 0x3BF9624: return 0x3B5D630;
    case 0x3BFA1A8: return 0x3B5E1B4;
    case 0x3BFAD10: return 0x3B5ED1C;
    case 0x3BFB878: return 0x3B5F884;
    case 0x3BFC3E0: return 0x3B603EC;
    case 0x3BFCF70: return 0x3B60F7C;
    case 0x3BFDB00: return 0x3B61B0C;
    case 0x3BFE594: return 0x3B625A0;
    case 0x4918DE8: return 0x488BB4C;
    case 0x4921F20: return 0x4894C84;
    case 0x4BD1600: return 0x4B14C40;
    case 0x4BD2144: return 0x4B15784;
    case 0x4BD2C88: return 0x4B162C8;
    case 0x4BD37CC: return 0x4B16E0C;
    case 0x4BD4310: return 0x4B17950;
    case 0x4BD4E54: return 0x4B18494;
    case 0x4BD5998: return 0x4B18FD8;
    case 0x4BD64DC: return 0x4B19B1C;
    case 0x4BD7020: return 0x4B1A660;
    case 0x4BD7B7C: return 0x4B1B1BC;
    case 0x4BD86D8: return 0x4B1BD18;
    case 0x4BD9234: return 0x4B1C874;
    case 0x4BD9DB8: return 0x4B1D3F8;
    case 0x4BDA93C: return 0x4B1DF7C;
    case 0x4BDB498: return 0x4B1EAD8;
    case 0x4BDC01C: return 0x4B1F65C;
    case 0x4BDCBA0: return 0x4B201E0;
    case 0x4BDD724: return 0x4B20D64;
    case 0x4D7ED90: return 0x4CAD878;
    case 0x4D7EDC4: return 0x4CAD8AC;
    case 0x4D7EDF8: return 0x4CAD8E0;
    case 0x4D7EF50: return 0x4CADA38;
    case 0x53B53B4: return 0x52F4D74;
    case 0x53B5648: return 0x52F5008;
    case 0x53B5C90: return 0x52F5650;
    case 0x53B5C94: return 0x52F5654;
    case 0x53B5C98: return 0x52F5658;
    case 0x53B5C9C: return 0x52F565C;
    case 0x53B5CA0: return 0x52F5660;
    case 0x53B6064: return 0x52F5A24;
    case 0x53B6068: return 0x52F5A28;
    case 0x53B606C: return 0x52F5A2C;
    default: return global;
    }
}

static inline uint32_t game_original(uint32_t global, uint32_t word) {
    if (!bunker_game_japanese) return word;
    switch (global) {
    case 0x53B5C90: return 0x9000f749u;
    case 0x53B5C94: return 0xf942b929u;
    case 0x53B5C98: return 0xa9427bfdu;
    case 0x53B6064: return 0x9000f749u;
    case 0x53B6068: return 0xf942b929u;
    case 0x53B606C: return 0x531f7901u;
    case 0x3808EDC: return 0x9453f09bu;
    default: return word;
    }
}

static inline uint32_t game_patched(uint32_t global, uint32_t word) {
    if (!bunker_game_japanese) return word;
    switch (global) {
    case 0x53B5C90: return 0x0b090101u;
    case 0x53B5C94: return 0x9000f749u;
    case 0x53B5C98: return 0xf942b929u;
    case 0x53B6064: return 0x0b090101u;
    case 0x53B6068: return 0x9000f749u;
    case 0x53B606C: return 0xf942b929u;
    case 0x3808EDC: return 0x97bdf8cdu;
    default: return word;
    }
}
#endif
