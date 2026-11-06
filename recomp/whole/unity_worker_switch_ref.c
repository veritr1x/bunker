#include "unity_worker_switch_cases.h"
extern void original_dispatch(uintptr_t,uintptr_t,uint64_t,struct Out*,uint64_t);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(int argc,char**argv){if(argc!=2||map_original(argv[1]))return 2;tls_canary=17;unsigned executions=0;
 for(unsigned i=0;i<sizeof(indices)/sizeof(*indices);i++)for(unsigned n=0;n<2;n++){
  seed(indices[i]);uint64_t before=hash_owned();struct Out out;memset(&out,0x5a,sizeof(out));original_dispatch(owned,dispatch_pc,incoming[n],&out,input_table(indices[i],n));
  if(out.target!=expected_target(indices[i])||!out.abi||hash_owned()!=before||out.fpcr!=0xc00000||out.fpsr!=0x0800009f||out.x9!=old_x9||out.x10!=old_x10||out.x22!=old_x22||out.x27!=input_table(indices[i],n))return 3;
  if(out.x8!=(indices[i]<=7?expected_target(indices[i]):indices[i]))return 4;
  record(indices[i],n,&out);executions++;
 }
 printf("ORIGINAL-UNITY-WORKER-SWITCH-PASS executions=%u TLS=%u\n",executions,tls_canary);return tls_canary!=17;
}
