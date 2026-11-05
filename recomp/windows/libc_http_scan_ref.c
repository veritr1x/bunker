#include "libc_http_scan_cases.h"
#include <errno.h>
extern int64_t guest_http_scan(const char*,unsigned,int*,int*,int*,int);
static _Thread_local volatile int tls_canary __attribute__((aligned(64)));
int main(void){tls_canary=17;for(unsigned form=0;form<2;++form)for(unsigned n=0;n<HTTP_SCAN_CASE_COUNT;++n){struct HttpScanBuffers out;HttpScanInitialize(&out);errno=123;int64_t result=guest_http_scan(http_scan_cases[n].input,http_scan_cases[n].format,(int*)(out.slots[0]+8),(int*)(out.slots[1]+8),(int*)(out.slots[2]+8),form);int error=errno;HttpScanRecord(n,form,result,error,&out);}if(tls_canary!=17)return 3;printf("HTTP-SCAN-BIONIC-PASS cases=%u records=%u TLS=%d\n",(unsigned)HTTP_SCAN_CASE_COUNT,(unsigned)HTTP_SCAN_CASE_COUNT*2,tls_canary);return 0;}
