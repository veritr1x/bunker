#include <sys/mman.h>
#include "leaf_rounding_cases.h"
extern void original_leaf_rounding(uintptr_t,uint64_t,uint64_t,struct FrameOutput*);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(int argc,char**argv){
 if(argc!=2||map_original(argv[1]))return 2;tls_canary=17;unsigned executions=0;
 for(unsigned sample=0;sample<24;sample++)for(unsigned mode=0;mode<16;mode++)for(unsigned initial=0;initial<2;initial++){
  const struct LeafInput*input=&leaf_inputs[sample];if(!normal_or_zero(input->value)||!normal_or_zero(input->scale))return 5;
  seed(sample);uint64_t before=object_hash();struct FrameOutput out;memset(&out,0x5a,sizeof(out));memcpy(out.vectors[0],&input->value,4);memcpy(out.vectors[1],&input->scale,4);
  uint64_t fpcr=((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22),fpsr=initial?0x0800009f:0;
  original_leaf_rounding(owned,fpcr,fpsr,&out);if(!out.abi_ok||object_hash()!=before||out.fpcr!=fpcr||out.nzcv!=0xa0000000)return 3;
  record(sample,mode,initial,&out);++executions;
 }
 printf("ORIGINAL-LEAF-ROUNDING-PASS executions=%u TLS=%u\n",executions,tls_canary);return tls_canary!=17;
}
