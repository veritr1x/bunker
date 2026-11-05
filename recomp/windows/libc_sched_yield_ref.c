#include <stdint.h>
#include <stdio.h>
struct YieldResult { int32_t status,error; int64_t widened; };
extern int64_t guest_sched_yield(int,int,struct YieldResult*);
static _Thread_local volatile int tls_canary __attribute__((aligned(64)));
int main(void){tls_canary=17;unsigned calls=0;
  for(int mode=0;mode<2;++mode)for(int n=0;n<8;++n){struct YieldResult out={-77,-88,-99};const int sentinel=123+n;
    if(guest_sched_yield(mode,sentinel,&out)!=0||out.status||out.widened||out.error!=sentinel)return 2;
    ++calls;
  }
  if(tls_canary!=17)return 3;
  printf("SCHED-YIELD-BIONIC-PASS calls=%u TLS=%d\n",calls,tls_canary);return 0;
}
