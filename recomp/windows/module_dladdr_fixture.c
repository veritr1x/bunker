#include <stdint.h>
extern unsigned char fixture_abs[];
__attribute__((visibility("default"))) uint64_t fixture_data=0x123456789abcdef0ULL;
static uint64_t local_data=0x8877665544332211ULL;
__attribute__((visibility("default"))) void *fixture_abs_pointer=fixture_abs+7;
__attribute__((visibility("default"))) void *fixture_regular_pointer=&fixture_data;
__attribute__((visibility("default"))) void *fixture_relative_pointer=&local_data;
__attribute__((noinline,visibility("default"))) uintptr_t fixture_abs_got(void){return (uintptr_t)fixture_abs;}
__attribute__((noinline,visibility("default"))) uint64_t fixture_function(uint64_t x){return x+fixture_data;}
__attribute__((noinline,visibility("default"))) uint64_t fixture_v1(uint64_t x){return x+1;}
__attribute__((noinline,visibility("default"))) uint64_t fixture_v2(uint64_t x){return x+2;}
__attribute__((noinline,visibility("default"))) uint64_t fixture_oldonly(uint64_t x){return x+3;}
__asm__(".symver fixture_v1,fixture_versioned@V1\n"
        ".symver fixture_v2,fixture_versioned@@V2\n"
        ".symver fixture_oldonly,fixture_hidden_only@V1\n");
