#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

typedef void (*fp_compare_call)(const char *, uint8_t *, const uint8_t *, const uint8_t *, uint64_t, uint64_t);
static const uint32_t fp_arith_edges32[] = {
    0, 0x80000000, 0x3f800000, 0xbf800000,
    1, 0x80000001, 0x007fffff, 0x807fffff, 0x00800000, 0x80800000,
    0x7f7fffff, 0xff7fffff, 0x7f800000, 0xff800000,
    0x7fc00000, 0xffc00000, 0x7fc12345, 0x7f800001, 0xff800001, 0x7fbfffff,
    0x3f800001, 0xbf800001, 0x3f7fffff, 0xbf7fffff, 0x00800001, 0x80800001,
    0x3f000000, 0xbf000000, 0x40000000, 0xc0000000, 0x40400000, 0xc0400000,
    0x40800000, 0xc0800000, 0x33000000, 0xb3000000, 0x33800000, 0xb3800000};
static const uint64_t fp_arith_edges64[] = {
    0, UINT64_C(0x8000000000000000), UINT64_C(0x3ff0000000000000), UINT64_C(0xbff0000000000000),
    1, UINT64_C(0x8000000000000001), UINT64_C(0x000fffffffffffff), UINT64_C(0x800fffffffffffff),
    UINT64_C(0x0010000000000000), UINT64_C(0x8010000000000000), UINT64_C(0x7fefffffffffffff), UINT64_C(0xffefffffffffffff),
    UINT64_C(0x7ff0000000000000), UINT64_C(0xfff0000000000000), UINT64_C(0x7ff8000000000000), UINT64_C(0xfff8000000000000),
    UINT64_C(0x7ff8123456789abc), UINT64_C(0x7ff0000000000001), UINT64_C(0xfff0000000000001), UINT64_C(0x7ff7ffffffffffff),
    UINT64_C(0x3ff0000000000001), UINT64_C(0xbff0000000000001), UINT64_C(0x3fefffffffffffff), UINT64_C(0xbfefffffffffffff),
    UINT64_C(0x0010000000000001), UINT64_C(0x8010000000000001), UINT64_C(0x3fe0000000000000), UINT64_C(0xbfe0000000000000),
    UINT64_C(0x4000000000000000), UINT64_C(0xc000000000000000), UINT64_C(0x4008000000000000), UINT64_C(0xc008000000000000),
    UINT64_C(0x4010000000000000), UINT64_C(0xc010000000000000), UINT64_C(0x3c90000000000000), UINT64_C(0xbc90000000000000),
    UINT64_C(0x3ca0000000000000), UINT64_C(0xbca0000000000000)};

#ifdef FP_RECIP_RANDOM_CASES
static uint64_t fp_recip_random(uint64_t *state) {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    return *state;
}
#endif

static int run_fp_compare_cases(fp_compare_call call) {
    const uint64_t initial[] = {0, 0x0800009f};
    const unsigned edges = sizeof(fp_arith_edges32) / sizeof(fp_arith_edges32[0]);
    uint8_t left[32], right[32], output[24];
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    for (unsigned test = 0; test < sizeof(fp_case_names) / sizeof(fp_case_names[0]); ++test) {
        for (unsigned round = 0; round < 4; ++round) {
            for (unsigned controls = 0; controls < 4; ++controls) {
                const uint64_t fpcr = ((uint64_t)round << 22) | ((uint64_t)controls << 24);
                for (unsigned flags = 0; flags < 2; ++flags) {
                    for (unsigned a = 0; a < edges; ++a) {
                        for (unsigned b = 0; b < edges; ++b) {
                            memset(left, 0xa5, sizeof(left));
                            memset(right, 0x5a, sizeof(right));
                            if (fp_case_widths[test] == 32) {
                                for (unsigned lane = 0; lane < 4; ++lane) {
                                    uint32_t x = fp_arith_edges32[(a + lane) % edges], y = fp_arith_edges32[(b + lane * 3) % edges];
                                    memcpy(left + lane * 4, &x, 4); memcpy(right + lane * 4, &y, 4);
                                }
                            } else {
                                for (unsigned lane = 0; lane < 2; ++lane) {
                                    uint64_t x = fp_arith_edges64[(a + lane) % edges], y = fp_arith_edges64[(b + lane * 3) % edges];
                                    memcpy(left + lane * 8, &x, 8); memcpy(right + lane * 8, &y, 8);
                                }
                            }
                            memset(output, 0, sizeof(output));
                            call(fp_case_names[test], output, left, right, fpcr, initial[flags]);
                            if (fwrite(output, 1, sizeof(output), stdout) != sizeof(output)) return 1;
                        }
                    }
                }
            }
        }
#ifdef FP_RECIP_RANDOM_CASES
        // A separate deterministic raw-bit sweep reaches arbitrary NaN
        // payloads and finite exponents/significands beyond the edge matrix.
        for (unsigned round = 0; round < 4; ++round) {
            for (unsigned controls = 0; controls < 4; ++controls) {
                const uint64_t fpcr = ((uint64_t)round << 22) | ((uint64_t)controls << 24);
                for (unsigned flags = 0; flags < 2; ++flags) {
                    uint64_t random = UINT64_C(0x465245435053);
                    for (unsigned sample = 0; sample < FP_RECIP_RANDOM_CASES; ++sample) {
                        memset(left, 0xa5, sizeof(left));
                        memset(right, 0x5a, sizeof(right));
                        if (fp_case_widths[test] == 32) {
                            for (unsigned lane = 0; lane < 4; ++lane) {
                                uint32_t x = (uint32_t)fp_recip_random(&random), y = (uint32_t)fp_recip_random(&random);
                                memcpy(left + lane * 4, &x, 4); memcpy(right + lane * 4, &y, 4);
                            }
                        } else {
                            for (unsigned lane = 0; lane < 2; ++lane) {
                                uint64_t x = fp_recip_random(&random), y = fp_recip_random(&random);
                                memcpy(left + lane * 8, &x, 8); memcpy(right + lane * 8, &y, 8);
                            }
                        }
                        memset(output, 0, sizeof(output));
                        call(fp_case_names[test], output, left, right, fpcr, initial[flags]);
                        if (fwrite(output, 1, sizeof(output), stdout) != sizeof(output)) return 1;
                    }
                }
            }
        }
#endif
    }
    return 0;
}
