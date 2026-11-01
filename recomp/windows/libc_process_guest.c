#include <stdint.h>
#include <time.h>
#include <unistd.h>
#include <errno.h>
_Static_assert(sizeof(clock_t)==8 && (clock_t)-1<0,"Android ARM64 signed64 clock_t");
_Static_assert(sizeof(long)==8,"Android ARM64 sysconf signed64 long");
_Static_assert(CLOCKS_PER_SEC==1000000,"Android CPU clock microseconds");
#define BUNKER_SYSCONF_NAME(symbol,value) _Static_assert(symbol==value,"pinned Android sysconf name: " #symbol);
#include "libc_sysconf_names.inc"
#undef BUNKER_SYSCONF_NAME
int guest_process_contract(void){return CLOCKS_PER_SEC;}
clock_t guest_process_clock(int indirect){
  if(indirect){clock_t (*volatile function)(void)=clock;return function();}
  return clock();
}
long guest_process_sysconf(int name,int indirect,int seed,int *observed_errno){
  errno=seed;
  long result;
  if(indirect){long (*volatile function)(int)=sysconf;result=function(name);}
  else result=sysconf(name);
  *observed_errno=errno;return result;
}
