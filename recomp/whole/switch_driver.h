#pragma once
#include <stdint.h>
#include <stdio.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
typedef uint64_t (*switch_call)(uint32_t, uint64_t);
static int run_switch_cases(switch_call call) {
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    const uint32_t selectors[] = {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,
                                 20,21,100,0x7fffffff,0x80000000,0xffffffff};
    uint64_t random = UINT64_C(0x51a7c4e55001);
    for (unsigned i=0;i<sizeof(selectors)/sizeof(selectors[0]);++i) {
        for (unsigned seed=0;seed<64;++seed) {
            random^=random<<13;random^=random>>7;random^=random<<17;
            uint64_t result=call(selectors[i],random);
            if(fwrite(&result,1,8,stdout)!=8)return 1;
        }
    }
    return 0;
}
