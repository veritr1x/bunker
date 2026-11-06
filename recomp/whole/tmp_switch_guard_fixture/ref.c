#include "cases.h"
extern void original_dispatch(uintptr_t,uintptr_t,uint64_t,struct Out*,uint64_t);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(int argc,char**argv){if(argc!=2||map_original(argv[1]))return 2;tls_canary=17;unsigned executions=0;
 for(unsigned p=0;p<2;p++)for(unsigned i=0;i<sizeof(indices)/sizeof(*indices);i++)for(unsigned n=0;n<2;n++){
  seed(indices[i]);uint64_t before=hash_owned();struct Out out;memset(&out,0x5a,sizeof(out));original_dispatch(owned,prefixes[p].start,incoming[n],&out,stack_value);
  if(out.target!=expected_target(p,indices[i])||!out.abi||hash_owned()!=before||out.fpcr!=0xc00000||out.fpsr!=0x0800009f)return 3;
  if(p==1&&(out.x22!=stack_value||out.x27!=(uint32_t)incoming[n]||out.x9!=0x3f800000))return 4;
  record(p,indices[i],n,&out);executions++;
 }
 printf("ORIGINAL-TMP-GUARD-PASS executions=%u TLS=%u\n",executions,tls_canary);return tls_canary!=17;
}
