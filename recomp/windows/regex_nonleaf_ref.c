#include <sys/mman.h>
#include "regex_nonleaf_cases.h"
extern void original_regex_call(unsigned);
static _Thread_local unsigned tls_canary __attribute__((aligned(64)));
int main(int argc,char**argv){if(argc!=2||regex_map(argv[1]))return 2;tls_canary=17;((unsigned char*)0x8799a452)[0]=1;unsigned records=0;for(unsigned which=0;which<2;which++)for(unsigned n=0;n<4;n++)for(unsigned profile=0;profile<2;profile++){regex_seed(which,n,profile);unsigned char before[0x4000];memcpy(before,(void*)regex_owned,sizeof(before));original_regex_call(which);if(!regex_check(before,which,profile)){fprintf(stderr,"ARM model failed %u %u %u\n",which,n,profile);return 3;}if(memcmp((void*)(regex_sp+0x60+272),(void*)(regex_owned+0x1c100),512))return 4;regex_record(which,n,profile);++records;}printf("REGEX-ARM-PASS records=%u TLS=%u\n",records,tls_canary);return records!=16||tls_canary!=17;}
