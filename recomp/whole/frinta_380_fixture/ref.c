#include <sys/mman.h>
#include "cases.h"
extern void original380(uintptr_t,uint64_t,uint64_t,struct Out*);
extern void width_callback(void),height_callback(void);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(int argc,char**argv){if(argc!=2||map_original(argv[1]))return 2;tls_canary=17;unsigned count=0;
for(unsigned n=0;n<sizeof(cases)/sizeof(*cases);n++)for(unsigned mode=0;mode<4;mode++)for(unsigned initial=0;initial<2;initial++){
 seed(n,(uintptr_t)width_callback,(uintptr_t)height_callback);uint64_t before=hashdata(),globals=globalhash();struct Out out;memset(&out,0x5a,sizeof(out));uint64_t fpcr=(uint64_t)mode<<22;
 original380(owned,fpcr,initial?0x0800009f:0,&out);
 if(!out.abi_ok||(hashdata()!=before||globalhash()!=globals)||!valid_counts(n)||out.fpcr!=fpcr)return 3;
 record(n,mode,initial,&out);count++;
}
printf("ORIGINAL380-PASS executions=%u TLS=%u\n",count,tls_canary);return tls_canary!=17;}
