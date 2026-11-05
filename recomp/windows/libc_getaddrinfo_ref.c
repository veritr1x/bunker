#include "libc_getaddrinfo_cases.h"
#include <errno.h>
extern int64_t guest_getaddrinfo(const char*,const char*,const struct GaiAddr*,struct GaiAddr**,int);
extern void guest_freeaddrinfo(struct GaiAddr*,int);
extern uintptr_t guest_gai_strerror(int,int);
static _Thread_local volatile int tls_canary __attribute__((aligned(64)));
int main(void){tls_canary=17;unsigned calls=0;for(unsigned i=0;i<GAI_CASE_COUNT;++i)for(unsigned mode=0;mode<2;++mode){struct GaiAddr hints=GaiHints(&gai_cases[i]);struct GaiAddr*output=(struct GaiAddr*)(uintptr_t)0x12340000;errno=123;int result=(int)guest_getaddrinfo(gai_cases[i].node,gai_cases[i].service,gai_cases[i].null_hints?0:&hints,&output,mode);int error=errno;if(!GaiRecord(i,mode,result,error,output))return 2;++calls;if(result==0){errno=123;guest_freeaddrinfo(output,mode);printf("FREE %u %u %d\n",i,mode,errno);++calls;}}
 for(unsigned mode=0;mode<2;++mode)for(unsigned i=0;i<GAI_ERROR_COUNT;++i){if(!GaiErrorRecord(mode,gai_errors[i],(const char*)guest_gai_strerror(gai_errors[i],mode)))return 3;++calls;}
 for(unsigned mode=0;mode<2;++mode){errno=123;guest_freeaddrinfo(0,mode);printf("FREE %u %u %d\n",(unsigned)GAI_CASE_COUNT,mode,errno);++calls;}if(tls_canary!=17)return 4;printf("GAI-BIONIC-PASS records=%u TLS=%d\n",calls,tls_canary);return 0;}
