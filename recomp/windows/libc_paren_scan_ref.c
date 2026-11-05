#include "libc_paren_scan_cases.h"
#include <errno.h>
extern int64_t guest_paren_scan(const char*,unsigned,int*,int*,int*,int);
static _Thread_local volatile int tls_canary __attribute__((aligned(64)));
int main(void){tls_canary=17;for(unsigned form=0;form<2;++form)for(unsigned n=0;n<PAREN_SCAN_CASE_COUNT;++n){struct ParenScanBuffers out;ParenScanInitialize(&out);errno=123;int64_t result=guest_paren_scan(paren_scan_cases[n].input,paren_scan_cases[n].format,(int*)(out.slots[0]+8),(int*)(out.slots[1]+8),(int*)(out.slots[2]+8),form);int error=errno;ParenScanRecord(n,form,result,error,&out);}if(tls_canary!=17)return 3;printf("PAREN-SCAN-BIONIC-PASS cases=%u records=%u TLS=%d\n",(unsigned)PAREN_SCAN_CASE_COUNT,(unsigned)PAREN_SCAN_CASE_COUNT*2,tls_canary);return 0;}
