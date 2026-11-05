#include <sys/mman.h>
#include "frame_rounding_cases.h"
extern void original_frame_rounding(uintptr_t,uint64_t,uint64_t,struct FrameOutput*);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(int argc,char**argv){
 if(argc!=2||map_original(argv[1]))return 2;tls_canary=17;unsigned executions=0;
 for(unsigned sample=0;sample<34;sample++)if(normal_geometry(sample))for(unsigned chain=0;chain<2;chain++)for(unsigned mode=0;mode<4;mode++)for(unsigned initial=0;initial<2;initial++){
  seed(sample,chain);uint64_t before=object_hash();struct FrameOutput out;memset(&out,0x5a,sizeof(out));
  uint64_t fpcr=((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22),fpsr=initial?0x0800009f:0;
  original_frame_rounding(owned,fpcr,fpsr,&out);
  if(!out.abi_ok||object_hash()!=before||get64(0x712b8b58)>>32||out.fpcr!=fpcr)return 3;
  if(sample<32?out.vectors[0][15]!=0:(out.result!=120||out.vectors[0][15]!=0x5a))return 4;
  record(sample,chain,mode,initial,&out);++executions;
 }
 printf("ORIGINAL-FRAME-ROUNDING-PASS executions=%u TLS=%u\n",executions,tls_canary);return tls_canary!=17;
}
