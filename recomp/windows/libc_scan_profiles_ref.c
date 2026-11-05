#include "libc_scan_profiles_cases.h"
#include <errno.h>
extern int64_t guest_scan_profiles(const char*,const char*,void*,void*,void*,void*);
static _Thread_local volatile int tls_canary __attribute__((aligned(64)));
int main(void){tls_canary=17;for(unsigned n=0;n<SCAN_CASE_COUNT;++n){struct ScanBuffers out;ScanInitialize(&out);errno=123;int64_t status=guest_scan_profiles(scan_cases[n].input,scan_formats[scan_cases[n].format],out.bytes[0]+8,out.bytes[1]+8,out.bytes[2]+8,out.bytes[3]+8);ScanRecord(n,(int)status,errno,&out);}if(tls_canary!=17)return 3;printf("SCAN-BIONIC-PASS records=%u TLS=%d\n",(unsigned)SCAN_CASE_COUNT,tls_canary);return 0;}
