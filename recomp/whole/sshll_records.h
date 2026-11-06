#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef void (*sshll_call)(const char *, uint8_t *, const uint8_t *);
static int run_sshll_records(sshll_call call) {
  static const uint64_t edges[] = {0, UINT64_MAX, 1, UINT64_C(0x8000000080000000),
    UINT64_C(0x7fffffff7fffffff), UINT64_C(0xaaaaaaaaaaaaaaaa),
    UINT64_C(0x5555555555555555), UINT64_C(0x0001000100010001),
    UINT64_C(0xff00ff00ff00ff00), UINT64_C(0x00ff00ff00ff00ff),
    UINT64_C(0xffff0000ffff0000), UINT64_C(0x0000ffff0000ffff),
    UINT64_C(0x8080808080808080), UINT64_C(0x7f7f7f7f7f7f7f),
    UINT64_C(0x8000000000000000), UINT64_C(0x0000000080000000)};
  for (unsigned test = 0; test < sizeof(case_names)/sizeof(case_names[0]); ++test) {
    for (unsigned seed = 0; seed < 256; ++seed) {
      uint8_t input_space[160], output_space[160];
      memset(input_space, 0x73, sizeof(input_space));
      memset(output_space, 0xab, sizeof(output_space));
      uint8_t *input = input_space + 16 + seed%16;
      uint8_t *output = output_space + 16 + (seed*7)%16;
      uint64_t random = UINT64_C(0x9e3779b97f4a7c15) ^ seed;
      for (unsigned lane = 0; lane < 16; ++lane) {
        random ^= random << 13; random ^= random >> 7; random ^= random << 17;
        uint64_t value = seed < 16 ? edges[(seed+lane)%16] : random;
        memcpy(input+lane*8, &value, 8);
      }
      uint64_t nzcv = (uint64_t)(seed & 15) << 28;
      uint64_t fpsr = (seed & 31) | ((uint64_t)(seed & 32) << 2) |
                      ((uint64_t)(seed & 64) << 21);
      uint64_t fpcr = ((uint64_t)(seed & 3) << 22) |
                      ((uint64_t)(seed & 4) << 22) |
                      ((uint64_t)(seed & 8) << 22);
      memcpy(input+64,&nzcv,8); memcpy(input+72,&fpsr,8); memcpy(input+80,&fpcr,8);
      uint8_t original[160];memcpy(original,input_space,sizeof(original));
      call(case_names[test],output,input);
      if (memcmp(input_space,original,sizeof(original))) return 2;
      for (unsigned byte=0;byte<sizeof(output_space);++byte)
        if ((output_space+byte<output||output_space+byte>=output+120)&&output_space[byte]!=0xab) return 3;
      printf("%s %u ",case_names[test],seed);
      for (unsigned byte=0;byte<128;++byte)printf("%02x",output[byte]);
      putchar('\n');
    }
  }
  return 0;
}
