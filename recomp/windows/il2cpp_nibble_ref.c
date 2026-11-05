#include <sys/mman.h>
#include "il2cpp_nibble_cases.h"
extern void original_nibble_call(uintptr_t,uint32_t,uint32_t,struct FormatStatus*,const struct FormatProfile*);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(int argc,char**argv){if(argc!=2||map_original(argv[1]))return 2;tls_canary=17;unsigned count=0;for(unsigned n=0;n<42;n++)for(unsigned profile=0;profile<2;profile++){format_seed(n,profile);unsigned char before[0x2000];memcpy(before,(void*)owned,sizeof(before));struct FormatStatus status={0};struct FormatCase c=format_case(n);original_nibble_call(owned,c.start,c.end,&status,&format_profiles[profile]);if(!status.abi||status.fpcr!=format_profiles[profile].fpcr||status.fpsr!=format_profiles[profile].fpsr||!format_check(before,n))return 3;format_record(n,profile,&status);++count;}printf("IL2CPP-NIBBLE-ARM-PASS records=%u TLS=%u\n",count,tls_canary);return count!=84||tls_canary!=17;}
