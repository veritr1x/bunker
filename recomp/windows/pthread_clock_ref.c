#include <time.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
extern int pthread_clock_direct(clockid_t,struct timespec*);
extern int pthread_clock_indirect(clockid_t,struct timespec*);
static _Thread_local volatile int tls_canary __attribute__((aligned(64)));
int main(void){tls_canary=17;unsigned calls=0;int(*queries[])(clockid_t,struct timespec*)={pthread_clock_direct,pthread_clock_indirect};
 for(unsigned mode=0;mode<2;++mode){
  for(int id=0;id<2;++id){struct timespec t={-77,-88};errno=123;int r=queries[mode](id,&t);++calls;if(r||errno!=123||t.tv_sec<0||t.tv_nsec<0||t.tv_nsec>=1000000000||(!t.tv_sec&&!t.tv_nsec))return 2;printf("RES %u %d %lld %lld\n",mode,id,(long long)t.tv_sec,(long long)t.tv_nsec);errno=123;r=queries[mode](id,NULL);++calls;if(r||errno!=123)return 3;}
  struct timespec unchanged={77,88};errno=0;int r=queries[mode](-1,&unchanged);++calls;if(r!=-1||errno!=EINVAL||unchanged.tv_sec!=77||unchanged.tv_nsec!=88)return 4;
  errno=0;r=queries[mode](-1,NULL);++calls;if(r!=-1||errno!=EINVAL)return 5;
 }
 if(tls_canary!=17)return 6;printf("PTHREAD-CLOCK-REFERENCE-PASS calls=%u TLS=%d\n",calls,tls_canary);return 0;
}
