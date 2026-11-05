#include "libc_inet_pton_cases.h"
#include <errno.h>
extern int64_t guest_inet_pton(int,const char*,void*,int);
static _Thread_local volatile int tls_canary __attribute__((aligned(64)));
int main(void){tls_canary=17;unsigned count=0;for(unsigned i=0;i<INET_CASE_COUNT;++i)for(unsigned mode=0;mode<2;++mode){struct InetBytes out;memset(&out,0xa5,sizeof(out));errno=123;int status=(int)guest_inet_pton(inet_cases[i].family,inet_cases[i].input,out.bytes+16,mode);InetRecord(i,mode,status,errno,&out);++count;}if(tls_canary!=17)return 3;printf("INET-BIONIC-PASS records=%u TLS=%d\n",count,tls_canary);return 0;}
