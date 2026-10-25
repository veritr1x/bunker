// The test matrix both sides run. Each line is one call; check.py compares the
// ARM64 reference, the recompiled x86_64 build and OpenSSL line by line.
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>

// Signatures read from the disassembly; encrypt's second argument is never used.
typedef uint32_t (*aes_enc_fn)(uint8_t *out, void *unused, const uint8_t *in, uint32_t len, const uint8_t *key,
                               uint32_t key_len, const uint8_t *iv, uint8_t padding);
typedef uint32_t (*aes_dec_fn)(uint8_t *out, const uint8_t *in, uint32_t len, const uint8_t *key, uint32_t key_len,
                               const uint8_t *iv, uint8_t padding);

#define BASE 0x10000000UL
#define LIB "/recomp/work/lib/libFastAES.so"

static void fill(uint8_t *p, size_t n, uint32_t seed) {
    for (size_t i = 0; i < n; i++) p[i] = (uint8_t)((seed = seed * 1103515245u + 12345u) >> 16);
}

static void hex(const char *label, const uint8_t *p, size_t n) {
    printf(" %s=", label);
    for (size_t i = 0; i < n; i++) printf("%02x", p[i]);
}

static int run_cases(aes_enc_fn enc, aes_dec_fn dec) {
    static const uint32_t key_lens[] = {16, 24, 32}, lens[] = {16, 37, 64, 1000};
    static const uint8_t paddings[] = {0, 2};
    uint8_t key[32], iv[16], in[1024], out[1040], back[1040];
    for (unsigned k = 0; k < 3; k++)
        for (unsigned l = 0; l < 4; l++)
            for (unsigned p = 0; p < 2; p++) {
                uint32_t seed = k * 100 + l * 10 + p;
                fill(key, sizeof key, seed + 1), fill(iv, sizeof iv, seed + 2), fill(in, lens[l], seed + 3);
                memset(out, 0, sizeof out);
                uint32_t n = enc(out, NULL, in, lens[l], key, key_lens[k], iv, paddings[p]);
                printf("enc key_len=%u len=%u padding=%u ret=%u", key_lens[k], lens[l], paddings[p], n);
                hex("key", key, key_lens[k]), hex("iv", iv, 16), hex("in", in, lens[l]), hex("out", out, n);
                printf("\n");
                memset(back, 0, sizeof back);
                uint32_t m = dec(back, out, n, key, key_lens[k], iv, paddings[p]);
                printf("dec key_len=%u len=%u padding=%u ret=%u", key_lens[k], n, paddings[p], m);
                hex("out", back, m);
                printf("\n");
            }
    return 0;
}
