#pragma once
#include <stdint.h>
#include <stdio.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
typedef uint64_t (*masked_call)(uint64_t, uint64_t);
static int run_masked_switch(masked_call call) {
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    const uint64_t selectors[] = {0,1,2,3,4,5,6,0x7fffffff,0x80000000,0xffffffff,
        UINT64_C(0x100000000),UINT64_C(0x100000001),UINT64_C(0x100000002),
        UINT64_C(0x100000003),UINT64_C(0x100000004),UINT64_C(0x100000005),
        UINT64_C(0x8000000100000003),UINT64_MAX};
    uint64_t random = UINT64_C(0x36ef5c);
    for(unsigned i=0;i<sizeof(selectors)/sizeof(selectors[0]);++i)
        for(unsigned seed=0;seed<64;++seed) {
            random^=random<<13;random^=random>>7;random^=random<<17;
            uint64_t value=call(selectors[i],random);
            if(fwrite(&value,1,8,stdout)!=8)return 1;
        }
    return 0;
}
