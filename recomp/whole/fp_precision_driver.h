#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
typedef void (*fp_compare_call)(const char *, uint8_t *, const uint8_t *, const uint8_t *, uint64_t, uint64_t);
#include "fp_precision_edges.h"
static uint64_t precision_input(unsigned sample, unsigned lane, unsigned width) {
    if (sample < FP_PRECISION_EDGE_COUNT) {
        unsigned index = (sample + lane * 7) % FP_PRECISION_EDGE_COUNT;
        return width == 32 ? precision_edges32[index % (sizeof(precision_edges32)/sizeof(*precision_edges32))] : precision_edges64[index % (sizeof(precision_edges64)/sizeof(*precision_edges64))];
    }
    uint64_t value = UINT64_C(0x243f6a8885a308d3) ^ ((uint64_t)(sample - FP_PRECISION_EDGE_COUNT) << 32) ^ lane;
    value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}
static int run_fp_compare_cases(fp_compare_call call) {
    const uint64_t initial[] = {0, 0x0800009f};
    const unsigned samples = FP_PRECISION_EDGE_COUNT + 256;
    uint8_t left[32], right[32], output[24];
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    for (unsigned test = 0; test < sizeof(fp_case_names) / sizeof(fp_case_names[0]); ++test) {
        for (unsigned mode = 0; mode < 16; ++mode) {
            uint64_t fpcr = (uint64_t)(mode & 3) << 22;
            if (mode & 4) fpcr |= UINT64_C(1) << 24;
            if (mode & 8) fpcr |= UINT64_C(1) << 25;
            for (unsigned flags = 0; flags < 2; ++flags) {
                for (unsigned sample = 0; sample < samples; ++sample) {
                    memset(left, 0xa5, sizeof(left)); memset(right, 0x5a, sizeof(right));
                    unsigned width = fp_case_widths[test];
                    for (unsigned lane = 0; lane < 128 / width; ++lane) {
                        uint64_t value = precision_input(sample, lane, width);
                        memcpy(left + lane * (width / 8), &value, width / 8);
                    }
                    memset(output, 0, sizeof(output));
                    call(fp_case_names[test], output, left, right, fpcr, initial[flags]);
                    if (fwrite(output, 1, sizeof(output), stdout) != sizeof(output)) return 1;
                }
            }
        }
    }
    return 0;
}
