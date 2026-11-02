#include <sys/time.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
_Static_assert(sizeof(struct timeval)==16 && offsetof(struct timeval,tv_usec)==8,"Android LP64 timeval");
_Static_assert(sizeof(time_t)==8 && sizeof(suseconds_t)==8,"signed64 Android wall time");
uint64_t guest_wall_time(struct timeval *out,int indirect){
  errno=123;int result;
  if(indirect){__typeof__(&gettimeofday) volatile query=gettimeofday;result=query(out,0);}
  else result=gettimeofday(out,0);
  return (uint64_t)(uint32_t)errno<<32|(uint32_t)result;
}
