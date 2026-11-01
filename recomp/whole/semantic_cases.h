#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef void (*semantic_call)(const char *, uint8_t *, const uint8_t *, uint64_t);
static int run_semantic_cases(semantic_call call) {
    static const uint64_t steps[] = {0, 1, 32, 64, 127};
    uint8_t input_space[160], output_space[160];
    for (unsigned test = 0; test < sizeof(case_names) / sizeof(case_names[0]); ++test) {
        for (unsigned seed = 0; seed < 256; ++seed) {
            uint8_t *input = input_space + seed % 16;
            uint8_t *output = output_space + (seed * 7) % 16;
            for (unsigned i = 0; i < 128; ++i) input[i] = (seed * 37 + i * 19) & 255;
            for (unsigned i = 0; i < 16; ++i) input[64 + i] = (seed + i * 13) & 255;
            memset(output_space, 0xab, sizeof(output_space));
            call(case_names[test], output, input, steps[seed % 5]);
            printf("%s %u ", case_names[test], seed);
            for (unsigned i = 0; i < 128; ++i) printf("%02x", output[i]);
            putchar('\n');
        }
    }
    return 0;
}
