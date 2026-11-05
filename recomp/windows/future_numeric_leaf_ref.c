#include <sys/mman.h>
#include "future_numeric_leaf_cases.h"
extern void original_future_leaf(uintptr_t,uint64_t,uint64_t,struct BatchOutput*,uintptr_t,uintptr_t,uintptr_t);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(int argc,char**argv){if(argc!=2||map_original(argv[1]))return 2;tls_canary=17;unsigned executions=0;
 for(unsigned fn=0;fn<4;fn++)for(unsigned sample=0;sample<samples(fn);sample++)for(unsigned alias=0;alias<aliases(fn);alias++)for(unsigned mode=0;mode<16;mode++)for(unsigned initial=0;initial<2;initial++){
  if(fn==1){for(unsigned i=0;i<6;i++)if(!normal_or_zero(vector_inputs[sample][i]))return 5;}else if(!normal_or_zero(scalar_inputs[sample]))return 5;
  seed(fn,sample);unsigned char before[0x1000];memcpy(before,(void*)owned,sizeof(before));struct BatchOutput out;memset(&out,0x5a,sizeof(out));if(fn!=1)memcpy(out.vectors[0],&scalar_inputs[sample],4);
  uint64_t fpcr=((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22),fpsr=initial?0x0800009f:0;
  original_future_leaf(destination(fn,alias),fpcr,fpsr,&out,heads[fn],owned+0x100,owned+0x200);if(!out.abi_ok||!unchanged_canaries(fn,alias,before)||out.fpcr!=fpcr)return 3;
  record(fn,sample,alias,mode,initial,&out);++executions;
 }printf("ORIGINAL-FUTURE-LEAF-PASS executions=%u TLS=%u\n",executions,tls_canary);return tls_canary!=17;}
