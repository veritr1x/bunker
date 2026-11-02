#pragma once
#include <stdint.h>
#include <stdio.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
typedef uint64_t (*snapshot_call)(uint64_t,uint64_t);
static int run_snapshot_switch(snapshot_call call){
#ifdef _WIN32
 _setmode(_fileno(stdout),_O_BINARY);
#endif
 const uint64_t inputs[]={0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,
  0x7fffffff,0x80000000,0xffffffff,UINT64_C(0x100000000),UINT64_C(0x100000001),
  UINT64_C(0x10000000f),UINT64_C(0x8000000000000000),UINT64_MAX-3,UINT64_MAX-2,UINT64_MAX-1,UINT64_MAX};
 uint64_t random=UINT64_C(0xabc4fb2d0);
 for(unsigned i=0;i<sizeof(inputs)/sizeof(*inputs);++i)for(unsigned seed=0;seed<128;++seed){
  random^=random<<13;random^=random>>7;random^=random<<17;
  uint64_t result=call(inputs[i],random);if(fwrite(&result,1,sizeof(result),stdout)!=sizeof(result))return 1;
 }
 return 0;
}
