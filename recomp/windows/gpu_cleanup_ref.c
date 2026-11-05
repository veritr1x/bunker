#include <sys/mman.h>
#include "gpu_cleanup_cases.h"
extern void original_gpu_cleanup(uintptr_t,uint64_t,uint64_t,struct CleanupOutput*);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(int argc,char**argv){if(argc!=2||map_original(argv[1]))return 2;tls_canary=17;unsigned n=0;unsigned char before[0x10000];
 const uintptr_t excluded[]={0x700ff000,0x7024c000,0x7048f000};for(unsigned i=0;i<3;i++)if(mprotect((void*)excluded[i],4096,PROT_NONE))return 3;
 for(unsigned sample=0;sample<CLEANUP_SAMPLES;sample++)for(unsigned layout=0;layout<2;layout++)for(unsigned mode=0;mode<16;mode++)for(unsigned initial=0;initial<2;initial++){
 seed(sample,layout);memcpy(before,(void*)owned,sizeof(before));struct CleanupOutput out;memset(&out,0x5a,sizeof(out));uint64_t fpcr=((uint64_t)(mode&3)<<22)|((uint64_t)(mode&12)<<22),fpsr=initial?0x0800009f:0;original_gpu_cleanup(owned,fpcr,fpsr,&out);
 if(!out.abi_ok||memcmp(before,(void*)owned,sizeof(before))||get64(0x7123d688)||out.fpcr!=fpcr||out.result!=owned)return 4;
 record(sample,layout,mode,initial,&out);++n;}printf("ORIGINAL-GPU-CLEANUP-PASS records=%u TLS=%u helpers=0\n",n,tls_canary);return tls_canary!=17||n!=CLEANUP_RECORDS;}
