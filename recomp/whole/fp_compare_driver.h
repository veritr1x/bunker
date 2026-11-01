#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

typedef void (*fp_compare_call)(const char *, uint8_t *, const uint8_t *, const uint8_t *, uint64_t, uint64_t);
static const uint32_t fp_edges32[] = {0, 0x80000000, 0x3f800000, 0xbf800000,
    1, 0x80000001, 0x007fffff, 0x807fffff, 0x00800000, 0x80800000,
    0x7f7fffff, 0xff7fffff, 0x7f800000, 0xff800000,
    0x7fc00000, 0xffc00000, 0x7fc12345, 0x7f800001, 0xff800001, 0x7fbfffff};
static const uint64_t fp_edges64[] = {0, UINT64_C(0x8000000000000000), UINT64_C(0x3ff0000000000000), UINT64_C(0xbff0000000000000),
    1, UINT64_C(0x8000000000000001), UINT64_C(0x000fffffffffffff), UINT64_C(0x800fffffffffffff),
    UINT64_C(0x0010000000000000), UINT64_C(0x8010000000000000), UINT64_C(0x7fefffffffffffff), UINT64_C(0xffefffffffffffff),
    UINT64_C(0x7ff0000000000000), UINT64_C(0xfff0000000000000), UINT64_C(0x7ff8000000000000), UINT64_C(0xfff8000000000000),
    UINT64_C(0x7ff8123456789abc), UINT64_C(0x7ff0000000000001), UINT64_C(0xfff0000000000001), UINT64_C(0x7ff7ffffffffffff)};
static int run_fp_compare_cases(fp_compare_call call) {
    const uint64_t modes[] = {0, UINT64_C(1) << 24, UINT64_C(1) << 25, UINT64_C(3) << 24};
    const uint64_t initial[] = {0, 0x0800009f};
    uint8_t left[32], right[32], output[24];
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    for (unsigned test = 0; test < sizeof(fp_case_names) / sizeof(fp_case_names[0]); ++test) {
        for (unsigned mode = 0; mode < 4; ++mode) {
            for (unsigned flags = 0; flags < 2; ++flags) {
                for (unsigned a = 0; a < 20; ++a) {
                    for (unsigned b = 0; b < 20; ++b) {
                        memset(left, 0xa5, sizeof(left));
                        memset(right, 0x5a, sizeof(right));
                        if (fp_case_widths[test] == 32) {
                            for (unsigned lane = 0; lane < 4; ++lane) {
                                uint32_t x = fp_edges32[(a + lane) % 20], y = fp_edges32[(b + lane * 3) % 20];
                                memcpy(left + lane * 4, &x, 4); memcpy(right + lane * 4, &y, 4);
                            }
                        } else {
                            for (unsigned lane = 0; lane < 2; ++lane) {
                                uint64_t x = fp_edges64[(a + lane) % 20], y = fp_edges64[(b + lane * 3) % 20];
                                memcpy(left + lane * 8, &x, 8); memcpy(right + lane * 8, &y, 8);
                            }
                        }
                        memset(output, 0, sizeof(output));
                        call(fp_case_names[test], output, left, right, modes[mode], initial[flags]);
                        if (fwrite(output, 1, sizeof(output), stdout) != sizeof(output)) return 1;
                    }
                }
            }
        }
    }
    return 0;
}
